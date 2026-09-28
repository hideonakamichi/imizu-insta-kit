#!/usr/bin/env python3
"""エージェントの実行記録 (.claude/db/agents.db) を 1 枚の HTML にする。

    python scripts/dashboard.py            # dashboard.html を作る
    python scripts/dashboard.py --open     # 作ってブラウザで開く

★特徴★
- Python の標準ライブラリだけで動く。pip install は不要
- 出力は自己完結した HTML 1 枚。サーバも CDN も要らないので、そのまま人に渡せる
- DB が空でも落ちない (これから使う人が最初に開いても大丈夫)

記録は scripts/start-reflection.sh が書き込む。列の意味は schema を参照。
tokens_in / tokens_out / cost_usd は現状どのエージェントも書いていないため、
埋まっているときだけ表示する (書くようにしたら自動で出る)。
"""
import sqlite3, os, sys, html, webbrowser
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, ".claude", "db", "agents.db")
OUT = os.path.join(ROOT, "dashboard.html")

# 役割ごとの色。エージェント名を変えてもここに足せば色がつく
COLORS = {"sync": "#5b8def", "writer": "#e0a53a", "reviewer": "#3fa679"}


def role_of(slug):
    s = (slug or "").lower()
    for k in COLORS:
        if k in s:
            return k
    return "other"


def q(con, sql, args=()):
    try:
        return con.execute(sql, args).fetchall()
    except sqlite3.Error:
        return []


def esc(v):
    return html.escape(str(v if v is not None else ""))


def bar(pct, color, h=8):
    pct = max(0, min(100, pct))
    return (f'<div class="bar"><span style="width:{pct:.1f}%;background:{color};height:{h}px"></span></div>')


def main():
    if not os.path.exists(DB):
        print(f"実行記録がまだありません: {DB}")
        print("エージェントを 1 回動かすと作られます。")
        return 1
    con = sqlite3.connect(DB)
    cols = {r[1] for r in q(con, "PRAGMA table_info(reflections)")}
    if not cols:
        print("reflections テーブルがありません。")
        return 1

    total = q(con, "select count(*) from reflections")[0][0]
    by_status = dict(q(con, "select status, count(*) from reflections group by status"))
    done = by_status.get("completed", 0)
    failed = sum(v for k, v in by_status.items() if k in ("aborted", "abandoned", "failed"))
    running = by_status.get("running", 0)
    mins = (q(con, "select sum(duration_ms) from reflections")[0][0] or 0) / 1000 / 60

    agents = q(con, """select agent_slug, count(*), round(avg(quality_score),1),
                              round(sum(duration_ms)/60000.0,0),
                              sum(case when status='completed' then 1 else 0 end)
                       from reflections group by agent_slug order by count(*) desc""")
    recent = q(con, """select id, agent_slug, status, quality_score, started_at, duration_ms, parent_run_id
                       from reflections order by id desc limit 20""")
    scores = q(con, "select id, agent_slug, quality_score from reflections where quality_score is not null order by id")
    learns = q(con, """select id, agent_slug, self_improvement from reflections
                       where self_improvement is not null and length(self_improvement) > 30
                       order by id desc limit 12""")
    errors = q(con, """select id, agent_slug, started_at, error_message from reflections
                       where error_message is not null order by id desc limit 10""")
    has_cost = bool(q(con, "select count(cost_usd) from reflections")[0][0]) if "cost_usd" in cols else False

    maxn = max([a[1] for a in agents], default=1)
    P = []
    A = P.append
    A(f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>エージェント実行ダッシュボード</title><style>
:root{{--bg:#faf9f7;--card:#fff;--line:#e6e2dc;--txt:#2d2a26;--soft:#6b6560}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--txt);font-family:'Hiragino Sans','Yu Gothic UI',Meiryo,system-ui,sans-serif;line-height:1.8}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 18px 70px}}
h1{{font-size:1.5rem;margin:0 0 4px}} h2{{font-size:1.05rem;margin:36px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--line)}}
.sub{{color:var(--soft);font-size:.85rem;margin:0 0 22px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.kpi b{{display:block;font-size:1.8rem;line-height:1.3}} .kpi span{{font-size:.8rem;color:var(--soft)}}
table{{width:100%;border-collapse:collapse;background:var(--card);font-size:.88rem}}
th,td{{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}}
th{{background:#f3f0ec;font-weight:700;white-space:nowrap}}
.bar{{background:#eeeae4;border-radius:99px;overflow:hidden;min-width:90px}}
.bar span{{display:block;border-radius:99px}}
.tag{{display:inline-block;font-size:.72rem;font-weight:700;padding:1px 8px;border-radius:99px}}
.ok{{background:#e4f0e7;color:#2f6b41}} .ng{{background:#fbe6e6;color:#a33}} .run{{background:#fdf3d6;color:#7a5c00}}
.learn{{background:var(--card);border:1px solid var(--line);border-left:4px solid #e0a53a;border-radius:8px;padding:10px 14px;margin:0 0 10px;font-size:.86rem;white-space:pre-wrap}}
.learn i{{display:block;font-style:normal;color:var(--soft);font-size:.75rem;margin-bottom:4px}}
.note{{color:var(--soft);font-size:.8rem}} .empty{{color:var(--soft);padding:14px}}
</style></head><body><div class="wrap">
<h1>エージェント実行ダッシュボード</h1>
<p class="sub">{esc(os.path.relpath(DB, ROOT))} を読み込み &middot; 作成 {datetime.now():%Y-%m-%d %H:%M}</p>
<div class="kpis">
  <div class="kpi"><b>{total}</b><span>実行回数</span></div>
  <div class="kpi"><b>{done}</b><span>完了</span></div>
  <div class="kpi"><b>{failed}</b><span>中断・失敗</span></div>
  <div class="kpi"><b>{mins:,.0f}<small style="font-size:.9rem"> 分</small></b><span>のべ稼働時間</span></div>
</div>""")
    if running:
        A(f'<p class="note">※ 実行中のまま記録が残っているものが {running} 件あります（途中で止まったものを含みます）。</p>')

    A("<h2>エージェント別</h2>")
    if agents:
        A("<table><tr><th>エージェント</th><th>実行数</th><th></th><th>完了率</th><th>平均スコア</th><th>のべ時間</th></tr>")
        for slug, n, avg, m, ok in agents:
            c = COLORS.get(role_of(slug), "#999")
            rate = (ok / n * 100) if n else 0
            A(f"<tr><td><b>{esc(slug)}</b></td><td>{n}</td><td style='width:34%'>{bar(n/maxn*100, c)}</td>"
              f"<td>{rate:.0f}%</td><td>{esc(avg) or '—'}</td><td>{int(m or 0):,} 分</td></tr>")
        A("</table>")
        A('<p class="note">査読担当の実行数が執筆担当より多い場合、差し戻し（再査読）が起きています。'
          'この 2 つが同数に近いほど「一発合格」が多い、と読めます。</p>')
    else:
        A('<p class="empty">まだ記録がありません。</p>')

    A("<h2>品質スコアの推移</h2>")
    if scores:
        w, h, pad = 900, 170, 26
        xs = len(scores)
        pts = []
        for i, (rid, slug, sc) in enumerate(scores):
            x = pad + (w - pad * 2) * (i / max(1, xs - 1))
            y = h - pad - (h - pad * 2) * (max(0, min(100, sc)) / 100)
            pts.append((x, y, COLORS.get(role_of(slug), "#999"), rid, sc))
        A(f'<svg viewBox="0 0 {w} {h}" style="width:100%;background:var(--card);border:1px solid var(--line);border-radius:12px">')
        for gv in (50, 75, 100):
            gy = h - pad - (h - pad * 2) * (gv / 100)
            A(f'<line x1="{pad}" y1="{gy:.0f}" x2="{w-pad}" y2="{gy:.0f}" stroke="#eeeae4"/>'
              f'<text x="4" y="{gy+4:.0f}" font-size="10" fill="#9a938c">{gv}</text>')
        A('<polyline fill="none" stroke="#cfc9c1" stroke-width="1.5" points="' +
          " ".join(f"{x:.0f},{y:.0f}" for x, y, *_ in pts) + '"/>')
        for x, y, c, rid, sc in pts:
            A(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3.5" fill="{c}"><title>#{rid} スコア {sc}</title></circle>')
        A("</svg>")
        A('<p class="note">左が古く、右が新しい実行です。点の色は担当の種類。'
          '下がった点は差し戻しが起きた回で、その原因が skill に書き足されているはずです。</p>')
    else:
        A('<p class="empty">スコアの記録がまだありません。</p>')

    A("<h2>学びの蓄積（self_improvement）</h2>")
    if learns:
        A('<p class="note">エージェントが実行後に自分で書き残した改善点です。'
          'ここに出たものを skill に反映していくと、同じ失敗が減っていきます。</p>')
        for rid, slug, txt in learns:
            t = (txt or "").strip()
            if len(t) > 420:
                t = t[:420] + " …"
            A(f'<div class="learn"><i>#{rid} {esc(slug)}</i>{esc(t)}</div>')
    else:
        A('<p class="empty">まだ記録がありません。</p>')

    A("<h2>直近の実行</h2>")
    if recent:
        A("<table><tr><th>#</th><th>エージェント</th><th>状態</th><th>スコア</th><th>開始</th><th>所要</th><th>親</th></tr>")
        for rid, slug, st, sc, sa, dur, par in recent:
            cls = "ok" if st == "completed" else ("run" if st == "running" else "ng")
            d = f"{dur/1000/60:.0f} 分" if dur else "—"
            A(f"<tr><td>{rid}</td><td>{esc(slug)}</td><td><span class='tag {cls}'>{esc(st)}</span></td>"
              f"<td>{esc(sc) or '—'}</td><td>{esc(sa)[:16]}</td><td>{d}</td><td>{esc(par) or '—'}</td></tr>")
        A("</table>")
        A('<p class="note">「親」は、その実行を呼び出した編集長の番号です。'
          '編集長 1 回に対して執筆と査読がぶら下がる形で記録されます。</p>')

    if errors:
        A("<h2>エラー</h2><table><tr><th>#</th><th>エージェント</th><th>日時</th><th>内容</th></tr>")
        for rid, slug, sa, msg in errors:
            m = (msg or "")[:180]
            A(f"<tr><td>{rid}</td><td>{esc(slug)}</td><td>{esc(sa)[:16]}</td><td>{esc(m)}</td></tr>")
        A("</table>")

    if not has_cost:
        A('<h2>まだ出せていないもの</h2><p class="note">'
          'トークン数と料金（tokens_in / tokens_out / cost_usd）は、テーブルに列はありますが'
          'どのエージェントも書き込んでいないため空です。記録するようにすれば、この画面に自動で出ます。</p>')

    A("</div></body></html>")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(P))
    print(f"作成しました: {os.path.relpath(OUT, ROOT)}  （記録 {total} 件）")
    if "--open" in sys.argv:
        webbrowser.open("file://" + OUT.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
