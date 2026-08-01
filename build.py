import json, pathlib
t = pathlib.Path('site/template.html').read_text()
t = t.replace('__PREDICTOR__', pathlib.Path('site/predictor.js').read_text())
t = t.replace('__VISUALS__', pathlib.Path('site/visuals.js').read_text())
for ph, f in [('__DATA__','outputs/findings.json'), ('__TOOL__','outputs/tool_data.json'),
              ('__MODEL__','outputs/model_results.json'), ('__LIVE__','outputs/live_model.json'), ('__DAYS__','outputs/days_grid.json'), ('__MAP__','outputs/map.json'), ('__PB__','outputs/per_borough.json'), ('__APPR__','outputs/approval_results.json'), ('__TDD__','outputs/text_deep_dive.json')]:
    t = t.replace(ph, json.dumps(json.load(open(f)), separators=(',',':')))
assert '__' not in t.replace('__proto__','')[:200] and '__DATA__' not in t and '__LIVE__' not in t
pathlib.Path('site/index.html').write_text(t)
lp = t.replace('<div class="wrap">', '<script>document.documentElement.setAttribute("data-theme","light")</script><div class="wrap">', 1)
pathlib.Path('/tmp/light_preview.html').write_text(lp)
print(f'built site/index.html  {len(t)/1e6:.2f} MB')
