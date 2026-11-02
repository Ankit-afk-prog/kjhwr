import json, urllib.request
B = "http://localhost:8000/api"
get = lambda p: json.load(urllib.request.urlopen(B + p))

m = get("/meta"); print("SOURCE:", m["data_source"], "| coverage:", m["coverage"])
a = get("/accuracy"); o = a["overall"]
print(f"\nN half-hours={o['n']}  MAE={o['mae']:.0f}  RMSE={o['rmse']:.0f}  bias={o['bias']:+.0f}")
print(f"wMAPE={o['wmape']*100:.1f}%  P90|err|={o['p90_abs']:.0f}  P95|err|={o['p95_abs']:.0f}")
print(f"error P5..P95 = {o['err_p05']:+.0f} .. {o['err_p95']:+.0f}")
w = max(a["by_day"], key=lambda x: x["mae"]); print(f"WORST DAY: delivery {w['delivery_date']} MAE={w['mae']:.0f}")
h = max(a["by_hour"], key=lambda x: x["mae"]); print(f"HARDEST HOUR: {h['hour']:02d}:00 MAE={h['mae']:.0f}")
hz = a["by_horizon"]; print(f"LEAD TIME: {hz[0]['lo']}-{hz[0]['hi']}h MAE={hz[0]['mae']:.0f}  ->  {hz[-1]['lo']}-{hz[-1]['hi']}h MAE={hz[-1]['mae']:.0f}")
print("DECISION LEADS USED (h):", [round(x,1) for x in a["decision_horizon_h"]])

d = get("/decision?decision_date=2026-01-15"); s = d["summary"]
print(f"\n15 JAN: energy={s['forecast_mwh']/1000:.1f} GWh avg={s['forecast_avg_mw']:.0f} MW peak={s['peak_mw']:.0f} MW @ {s['peak_time'][11:16]}")
print(f"buffer={s['buffer_mwh']/1000:.1f} GWh  revision={s.get('revision_mwh',0)/1000:+.1f} GWh (slots {s.get('revision_slots')}/48)")
da = s["day_accuracy"]; print(f"that day: MAE={da['mae']:.0f} bias={da['bias']:+.0f}")
print("band:", d["bands"])