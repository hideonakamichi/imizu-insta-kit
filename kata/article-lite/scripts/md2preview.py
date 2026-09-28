# article_md → 簡易プレビュー HTML (DialogueBubble 風)
import re, sys, html, json

src, dst, title = sys.argv[1], sys.argv[2], sys.argv[3]
md = open(src, encoding='utf-8').read()

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'&lt;mark&gt;(.+?)&lt;/mark&gt;', r'<mark>\1</mark>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    return s

lines = md.split('\n')
out = []
i = 0
in_dir = None
while i < len(lines):
    line = lines[i]
    s = line.strip()
    if s.startswith('<!--'):
        while i < len(lines) and '-->' not in lines[i]:
            i += 1
        i += 1
        continue
    if not s:
        i += 1
        continue
    m = re.match(r':::(\w+)(?:\{title="([^"]*)"\})?', s)
    if m and s != ':::':
        cls = m.group(1)
        t = m.group(2) or {'pointbox': 'ポイント', 'warning': '注意', 'steps': 'ステップ'}.get(cls, cls)
        out.append(f'<div class="box {cls}"><div class="box-title">{html.escape(t)}</div>')
        in_dir = cls
        i += 1
        continue
    if s == ':::':
        out.append('</div>')
        in_dir = None
        i += 1
        continue
    if s.startswith('## '):
        out.append(f'<h2>{inline(s[3:])}</h2>')
        i += 1
        continue
    if s.startswith('### '):
        out.append(f'<h3>{inline(s[4:])}</h3>')
        i += 1
        continue
    m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', s)
    if m:
        out.append(f'<img src="{m.group(2)}" alt="{html.escape(m.group(1))}">')
        i += 1
        continue
    if s.startswith('|'):
        rows = []
        while i < len(lines) and lines[i].strip().startswith('|'):
            cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
            if not all(re.match(r'^:?-+:?$', c) for c in cells):
                rows.append(cells)
            i += 1
        if rows:
            thead = '<tr>' + ''.join(f'<th>{inline(c)}</th>' for c in rows[0]) + '</tr>'
            tbody = ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in rows[1:])
            out.append(f'<table>{thead}{tbody}</table>')
        continue
    m = re.match(r'\*\*(みさき|藤井)\*\*:\s*(.*)', s)
    if m:
        who = m.group(1)
        side = 'left' if who == 'みさき' else 'right'
        label = 'みさき' if who == 'みさき' else '藤井先生'
        out.append(f'<div class="bubble {side}"><div class="who">{label}</div><div class="talk">{inline(m.group(2))}</div></div>')
        i += 1
        continue
    if in_dir and (s.startswith('- ') or re.match(r'^\d+\. ', s)):
        items = []
        while i < len(lines) and (lines[i].strip().startswith('- ') or re.match(r'^\d+\. ', lines[i].strip())):
            items.append(f'<li>{inline(re.sub(r"^(- |\d+\. )", "", lines[i].strip()))}</li>')
            i += 1
        out.append('<ul>' + ''.join(items) + '</ul>')
        continue
    out.append(f'<p>{inline(s)}</p>')
    i += 1

css = """
body{font-family:'Hiragino Sans','Yu Gothic',Meiryo,sans-serif;max-width:760px;margin:0 auto;padding:24px 16px;background:#faf9f7;color:#333;line-height:1.8}
h1{font-size:1.4rem;border-left:6px solid #f472b6;padding-left:12px}
h2{font-size:1.2rem;background:#fdf2f8;border-radius:8px;padding:10px 14px;margin-top:2.2em}
h3{font-size:1.05rem}
.bubble{display:flex;flex-direction:column;margin:14px 0;max-width:88%}
.bubble.left{align-items:flex-start}
.bubble.right{align-items:flex-end;margin-left:auto}
.who{font-size:.75rem;color:#888;margin-bottom:2px}
.talk{padding:12px 16px;border-radius:14px;background:#eee}
.left .talk{background:#fff;border:1px solid #e5e5e5;border-top-left-radius:4px}
.right .talk{background:#dcfce7;border-top-right-radius:4px}
mark{background:#fef08a;padding:0 2px}
img{max-width:100%;border-radius:10px;margin:12px 0;border:1px solid #eee}
table{border-collapse:collapse;width:100%;margin:14px 0;background:#fff;font-size:.9rem}
th,td{border:1px solid #ddd;padding:8px 10px;text-align:left;word-break:break-all}
th{background:#fdf2f8}
.box{border:2px solid #fca5a5;border-radius:10px;margin:16px 0;background:#fff;overflow:hidden}
.box-title{background:#ef4444;color:#fff;font-weight:700;padding:6px 14px;font-size:.9rem}
.box p,.box ul{margin:10px 14px}
.box.steps{border-color:#93c5fd}
.box.steps .box-title{background:#3b82f6}
.note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;font-size:.85rem;color:#92400e;margin-bottom:20px}
"""
doc = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style></head><body>
<div class="note">📝 簡易プレビュー (本番の Next.js デザインとは異なります)。DB の article_md をそのまま変換したものです。</div>
<h1>{html.escape(title)}</h1>
{''.join(out)}
</body></html>"""
open(dst, 'w', encoding='utf-8').write(doc)
print(f"OK: {dst}")
