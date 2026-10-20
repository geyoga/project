"""Generate a self-contained, read-only apartment watchlist page."""

import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import DATA_DIR  # noqa: E402
from services.storage import (  # noqa: E402
    get_current_listings,
    get_latest_crawl_run,
)

OUTPUT = Path(os.getenv("APARTMENT_AGENT_WATCHLIST", ROOT / "watchlist" / "index.html"))
INTERVAL_MINUTES = int(os.getenv("WATCHLIST_UPDATE_INTERVAL_MINUTES", "360"))
DISPLAY_ZONE = ZoneInfo("Asia/Jakarta")

ROMAJI = {
    "上和田": "Kamiwada", "奈良北": "Narakita", "相模台": "Sagamidai",
    "霧が丘グリーンタウン": "Kirigaoka Green Town", "すすき野": "Susukino",
    "えびな": "Ebina", "くぬぎ台": "Kunugidai", "さがみ野さくら": "Sagaminosakura",
    "アーバンハイツ菅生ヶ丘": "Urban Heights Sugaoka", "グリーンヒル鴨志田中央": "Green Hill Kamoshida Chuo",
    "コンフォールさがみ南": "Confort Sagami-minami", "コンフォール南日吉": "Confort Minamihiyoshi",
    "コンフォール生田菅生ヶ丘": "Confort Ikuta Sugaoka", "コンフォール西寺尾": "Confort Nishi-Terao",
    "コンフォール鴨池公園": "Confort Kamoike Park", "サンラフレ百合ヶ丘": "Sunlafre Yurigaoka",
    "サンヴァリエ日吉": "Sunvalier Hiyoshi", "プロムナード本牧": "Promenade Honmoku",
    "プロムナード矢部": "Promenade Yabe", "ベイシティ本牧南": "Bay City Honmokuminami",
    "左近山": "Sakonyama", "左近山第三": "Sakonyama Dai-san", "東戸塚ビューハイツ": "Higashi-Totsuka View Heights",
    "横浜山手コンフォール滝ノ上": "Yokohama Yamate Confort Takinoue", "橋本四丁目": "Hashimoto 4-chome",
    "港北ニュータウン　サントゥール中川": "Kohoku New Town Santour Nakagawa",
    "港北ニュータウン　メゾンふじのき台": "Kohoku New Town Maison Fujinokidai",
    "港北ニュータウン　山田富士公園ハイツ": "Kohoku New Town Yamada Fuji Park Heights",
    "虹ヶ丘": "Nijigaoka", "西ひかりが丘": "Nishi Hikarigaoka", "西菅田": "Nishi-Sugata",
}


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def display_time(value):
    moment = parse_time(value)
    if not moment:
        return "Not available"
    return moment.astimezone(DISPLAY_ZONE).strftime("%Y-%m-%d %H:%M WIB")


def listing_payload(row):
    details = json.loads(row.get("latest_json") or "{}")
    details.update(row)
    details["property_romaji"] = ROMAJI.get(details.get("property"), "")
    details.pop("latest_json", None)
    return details


def main():
    rows = [listing_payload(row) for row in get_current_listings()]
    crawl = get_latest_crawl_run()
    last_updated = crawl.get("finished_at") if crawl else max(
        (row.get("last_seen_at") for row in rows), default=None
    )
    updated_at = parse_time(last_updated) or datetime.now(timezone.utc)
    next_update = updated_at + timedelta(minutes=INTERVAL_MINUTES)
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    generated = TEMPLATE.replace("__APARTMENTS__", payload)
    generated = generated.replace("__LAST_UPDATED__", html.escape(display_time(last_updated)))
    generated = generated.replace("__NEXT_UPDATE__", html.escape(display_time(next_update.isoformat())))
    generated = generated.replace("__COUNT__", str(len(rows)))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"WATCHLIST={OUTPUT} LISTINGS={len(rows)}")


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Apartment Watchlist</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#18181b;background:#fafafa;--border:#e4e4e7;--muted:#71717a;--card:#fff;--primary:#18181b;--radius:12px}*{box-sizing:border-box}body{margin:0;background:#fafafa}.wrap{max-width:1240px;margin:auto;padding:32px 20px 56px}h1{margin:0 0 6px;font-size:clamp(1.7rem,4vw,2.25rem);letter-spacing:-.04em}.sub,.muted{color:var(--muted)}.sub{margin:0 0 24px}.stats{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:24px}.stat{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:13px 16px;min-width:180px}.stat b{display:block;font-size:1.1rem;margin-top:4px}.filters{display:grid;grid-template-columns:2fr repeat(5,1fr);gap:10px;margin-bottom:24px}.control{height:40px;border:1px solid var(--border);border-radius:8px;background:white;padding:0 11px;font:inherit;min-width:0}select.control{appearance:none;padding-right:34px;background:white url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%2371717a' stroke-linecap='round' stroke-linejoin='round' stroke-width='2'%3E%3Cpath d='m4 6 4 4 4-4'/%3E%3C/svg%3E") no-repeat right 11px center}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px;box-shadow:0 1px 2px #00000008}.cardtop{display:flex;justify-content:space-between;gap:12px}.card h2{font-size:1.05rem;margin:0 0 4px}.badge{color:#15803d;background:#dcfce7;border-radius:999px;padding:4px 9px;font-size:.9rem;font-weight:700;line-height:1;white-space:nowrap;align-self:start}.price{font-size:1.35rem;font-weight:700;margin:17px 0 12px}.details{display:grid;grid-template-columns:1fr 1fr;gap:9px;border-top:1px solid var(--border);padding-top:13px}.detail span{display:block;color:var(--muted);font-size:.76rem}.detail b{font-size:.92rem}.actions{display:flex;gap:8px;margin-top:17px}.button{display:inline-block;border-radius:8px;padding:9px 12px;text-decoration:none;font-size:.88rem}.primary{background:var(--primary);color:white}.secondary{border:1px solid var(--border);color:var(--primary)}.empty{text-align:center;padding:48px;color:var(--muted);grid-column:1/-1}.footer{margin-top:26px;color:var(--muted);font-size:.8rem}@media(max-width:900px){.filters{grid-template-columns:repeat(3,1fr)}}@media(max-width:560px){.wrap{padding:24px 14px}.filters{grid-template-columns:1fr 1fr}.filters input{grid-column:1/-1}.stats{gap:8px}.stat{flex:1;min-width:140px}.cards{grid-template-columns:1fr}}
</style></head>
<body><main class="wrap"><header><h1>Apartment Watchlist</h1><p class="sub">Current UR apartments for commuting to Futako-Tamagawa</p><div class="stats"><div class="stat">Current listings<b id="count">__COUNT__</b></div><div class="stat">Last updated<b>__LAST_UPDATED__</b></div><div class="stat">Next expected update<b>__NEXT_UPDATE__</b></div></div></header>
<section class="filters" aria-label="Filter apartments"><input class="control" id="search" placeholder="Search property, room, station..." aria-label="Search"><select class="control" id="layout"><option value="">All layouts</option></select><select class="control" id="property"><option value="">All properties</option></select><input class="control" id="maxPrice" type="number" placeholder="Max ¥ / month" aria-label="Maximum monthly cost"><input class="control" id="minArea" type="number" placeholder="Min m²" aria-label="Minimum area"><select class="control" id="sort" aria-label="Sort"><option value="score">Highest score</option><option value="price">Lowest cost</option><option value="area">Largest area</option><option value="commute">Shortest commute</option></select></section>
<p class="muted" id="summary"></p><section class="cards" id="cards"></section><p class="footer">Availability is based on the last successful UR crawl. Confirm details on the official UR page before applying.</p></main>
<script>const apartments=__APARTMENTS__;const $=id=>document.getElementById(id);const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const value=(x,empty='Not available')=>esc(x===null||x===undefined||x===''?empty:x);const yen=x=>x==null?'Not available':'¥'+Number(x).toLocaleString();const url=x=>{try{let u=new URL(x);return u.protocol==='https:'&&u.hostname.endsWith('ur-net.go.jp')?esc(u.href):'#'}catch{return '#'}};const options=(id,key,label=x=>x)=>{[...new Set(apartments.map(x=>x[key]).filter(Boolean))].sort().forEach(x=>$(id).insertAdjacentHTML('beforeend',`<option value="${value(x)}">${value(label(x))}</option>`))};options('layout','layout');options('property','property',x=>apartments.find(a=>a.property===x).property_romaji||x);function render(){let q=$('search').value.toLowerCase(),layout=$('layout').value,property=$('property').value,max=+$('maxPrice').value,min=+$('minArea').value;let list=apartments.filter(x=>(!q||[x.property,x.property_romaji,x.room,x.primary_station,x.train_line,x.layout].join(' ').toLowerCase().includes(q))&&(!layout||x.layout===layout)&&(!property||x.property===property)&&(!max||x.monthly_total<=max)&&(!min||x.area_m2>=min));let sort=$('sort').value;list.sort((a,b)=>sort==='price'?(a.monthly_total||Infinity)-(b.monthly_total||Infinity):sort==='area'?(b.area_m2||0)-(a.area_m2||0):sort==='commute'?(a.total_commute_minutes||Infinity)-(b.total_commute_minutes||Infinity):(b.score||0)-(a.score||0));$('count').textContent=list.length+'/'+apartments.length;$('summary').textContent=`Showing ${list.length} of ${apartments.length} apartments`;$('cards').innerHTML=list.length?list.map(x=>`<article class="card"><div class="cardtop"><div><h2>${value(x.property)}</h2><div class="muted">${value(x.property_romaji)}${x.property_romaji?" · ":""}${value(x.room)}</div></div><span class="badge">${value(x.score)}</span></div><div class="price">${yen(x.monthly_total)}<small class="muted"> / month</small></div><div class="details"><div class="detail"><span>Rent + fee</span><b>${yen(x.rent)} + ${yen(x.management_fee)}</b></div><div class="detail"><span>Layout / area</span><b>${value(x.layout)} · ${value(x.area_m2)} m²</b></div><div class="detail"><span>Floor / orientation</span><b>${value(x.floor)} · ${value(x.orientation)}</b></div><div class="detail"><span>Building age</span><b>${x.building_age_estimate_years!=null?value(x.building_age_estimate_years)+' years':'Not available'}</b></div><div class="detail"><span>Station access</span><b>${value(x.primary_station)} · ${x.station_walk_minutes!=null?value(x.station_walk_minutes)+' min walk':'Not available'}</b></div><div class="detail"><span>Train line</span><b>${value(x.train_line)}</b></div><div class="detail"><span>Commute</span><b>${x.total_commute_minutes!=null?value(x.total_commute_minutes)+' min':'Not available'}</b></div><div class="detail"><span>Transfers</span><b>${value(x.transfers)}</b></div><div class="detail"><span>Elevator</span><b>${x.elevator==null?'Not available':x.elevator?'Yes':'No'}</b></div><div class="detail"><span>Bath / toilet separate</span><b>${x.bath_toilet_separate==null?'Not available':x.bath_toilet_separate?'Yes':'No'}</b></div></div><div class="actions"><a class="button primary" href="${url(x.source_url)}" target="_blank" rel="noopener">Open UR listing ↗</a></div></article>`).join(''):'<div class="empty">No apartments match these filters.</div>'}document.querySelectorAll('.control').forEach(x=>x.addEventListener('input',render));render();</script></body></html>'''


if __name__ == "__main__":
    main()
