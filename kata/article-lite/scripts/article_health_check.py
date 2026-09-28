#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公開済み記事の定期点検 (機械チェック層)

呼び出しは scripts/article-health-check.sh 経由を推奨 (環境変数・引数変換を行うため)。

検出コード:
  M01 official_url / source_url の到達性
  M02 本文中の外部 URL の到達性
  M03 図解画像 URL の到達性
  M04 内部リンク (/support/{id}) の実在性・公開状態
  M05 対象者の断定・過度の一般化 (writer skill 「対象者の断定禁止」の再走査)
  M06 根拠なし全国傾向表現 (reviewer E19 の再走査)
  M07 免責注意書きの時点表記 (欠落 / 陳腐化)
  M08 updated_at からの経過日数
  M09 年度リテラル (旧年度の残存 / 未来年度の言及)
  M10 reviewer_verifications の欠落・陳腐化
  M11 前回メンテナンス点検からの経過 (research_notes.maintenance_checks)
  M12 DB の amount_max と本文金額の不一致
  M13 表示崩れ・AI 臭フレーズ (全角コロン / HH:MM / mark 未閉じ / ディレクティブ開閉 / 禁止フレーズ)
  M14 図解画像の目視キュー (★機械判定不能・人が Read で見る★)
  M15 alt テキストと本文の数値不一致疑い (図だけ直して alt が旧のまま、の検出)
  M16 時期・回数・期限の断定表現の抽出 (一次情報照合キュー)
  M17 電話番号の抽出 (一次情報照合キュー)
  M18 図解画像の他記事との混線 (ファイル名 prefix 不一致 / URL の使い回し / 画像バイナリの重複)
  M19 役所言葉の残存 (article_title / summary / みさきの発言 / 見出し。★藤井の解説は対象外★)
  M20 危険語 = 平易化のときに正確性を落としやすい表現 (★藤井の解説も対象★)
  M21 制度タイプ別の必須項目もれ (supports.category から型を判定)
  M22 記事末尾の構成順 (基本情報まとめ → 併用できる制度 → よくある質問 → 公式情報・問い合わせ先)

M14 / M16 / M17 は「機械では正誤を判定できないので人 (または AI) が一次情報に当たる対象を列挙する」
ためのキューであり、件数が 0 でないことが異常を意味するわけではない。

M20 も同じ性格の「再確認せよ」シグナルで、禁止ではない。本当に毎月振り込まれる制度・本当に
所得制限がない制度もあるため、CRIT ではなく WARN (吹き出し内は INFO) に留めている。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

CRIT, WARN, INFO = "CRIT", "WARN", "INFO"

# ---------------------------------------------------------------------------
# 検出パターン
# ---------------------------------------------------------------------------

# M05: 対象者の断定・過度の一般化 (support-article-writer skill 「対象者の断定禁止」)
ASSERTION_PATTERNS = [
    (r"(すべて|全て)の(家庭|世帯|ひとり親|方|人)が(対象|もらえ|受け取れ|支給)", "すべての〜が対象 型の断定"),
    (r"全員が(対象|もらえ|受け取れ)", "全員が対象 型の断定"),
    (r"(誰|だれ)でも(もらえ|受け取れ|対象|申請できま)", "誰でも 型の断定"),
    (r"に(住んで|お住まい)(いる|の)だけで", "居住だけを要件とする断定 (記事11 の実例)"),
    (r"だけで(年間|年|月)?[0-9][0-9,]*(万)?円", "「〜だけで N 円」型の断定 (記事11 の実例)"),
    (r"無条件で(もらえ|受け取れ|対象)", "無条件 型の断定"),
    (r"必ず(もらえ|受け取れ|受給できま|対象になりま|支給されま)", "必ず 型の断定"),
    (r"自動的に(もらえ|受け取れ|支給されま)", "自動支給の断定 (申請主義の制度が多い)"),
    (r"所得制限(は)?(ありません|なし|なく)", "「所得制限なし」の単独記述 (所得以外の要件の注記が必要)"),
    (r"(該当|対象)すれば(必ず|全員)", "該当すれば必ず 型の断定"),
]

# M06: 根拠なし全国傾向表現 (reviewer skill E19 と同期 + writer skill の禁止表現)
# M06: 根拠のない全国傾向。
# ★2026-07-27 追記の経緯★
#   当初は「多くの自治体」「ほとんどの自治体」の完全一致だけを見ていた。
#   ところが就学援助の記事 (id=21) の査読で、
#     「対象になっている自治体が多い」「締切が早いことが多い」
#   という ★語順を変えた同じ主張★ がすり抜けていた。
#   後者は根拠が神戸市1件だけなのに4箇所で反復されていた。
#   禁止語を並べるだけでは、自然な言い換えで再発する。
#   ※ここを直すときは reviewer skill の E19 も同じ内容に揃えること。
NATIONWIDE_PATTERNS = [
    # 「自治体」を主語にした形
    r"多くの自治体",
    r"ほとんどの自治体",
    r"ほぼすべての自治体",
    r"自治体が増えて",
    r"自治体がほとんど",
    r"自治体が多い",
    r"自治体も多い",
    # 主語を伏せて「〜が多い」で言う形 (今回すり抜けたパターン)
    r"ことが多い",
    r"ケースが多い",
    r"場合が多い",
    r"ところが多い",
    # 傾向として語る形
    r"が一般的です",
    r"一般的には",
    r"のが通例",
    r"増えています",
    r"増えつつ",
    # 量をぼかす副詞
    r"たいてい",
    # ★「おおむね」は入れない★ 「おおむね136万円以下」のような金額の概算に使われ、
    #   全国傾向の主張ではないため誤検出になる (実際に7件の誤検出を出した)
    r"大半(の|は)",
    r"多くの方が",
    r"よくあるケースです",
]

# 同じ文に具体例や出典があれば「根拠を示している」ので警告を弱める。
# ★禁止ではなく「根拠を示せ」の警告にする★ ため。
#   国の統計がある等、本当に「多い」と言える場合まで書けなくしてはいけない。
EVIDENCE_RE = re.compile(
    r"(市|区|町|村)(では|は|の場合)"      # 「神戸市では」「大田区は」
    r"|によると|による調査|統計|調査結果"
    r"|https?://"
    r"|厚生労働省|文部科学省|こども家庭庁|国税庁|日本年金機構"
)

# M13: AI 臭フレーズ (support-article-writer skill の禁止リスト)
AI_PHRASES = [
    "することができます",
    "幅広く",
    "包括的に",
    "網羅的に",
    "一助となれば",
    "いかがでしたでしょうか",
    "まとめると以下のようになります",
    "整理すると",
    "でございます",
]

# M16: 時期・回数・期限の断定 (記事13「年2回の定期募集」= 実際は年4回、記事11「令和9年4月申請分まで」)
SCHEDULE_PATTERNS = [
    r"年[0-9１-９]回",
    r"[0-9１-９]{1,2}月と[0-9１-９]{1,2}月",
    r"毎年[0-9１-９]{1,2}月",
    r"奇数月|偶数月",
    r"令和[0-9０-９]{1,2}年[0-9０-９]{1,2}月(申請分)?まで",
    r"[0-9０-９]{4}年[0-9０-９]{1,2}月(申請分)?まで",
    r"締切|締め切り|受付終了",
]

# M19: 役所言葉 (support-article-writer skill 「読者の言葉で書くルール」と同期)
#
#   このサイトの skill 群は補助金エージェント (経営者向け) から派生したため語彙が役所寄りに
#   なりやすい。読者はその対極 (時間もお金も余裕がないひとり親) なので、読者が最初に読む面
#   ── article_title / summary / みさきの発言 / 見出し ── からは役所語を排除する。
#   ★藤井 (社労士) の解説は制度用語を使ってよいので、この検出の対象外★
#
# (役所の言葉, 言い換え) — 正式名称・「」引用・【】・かっこ説明は検出前にマスクされる
BUREAU_TERMS: list[tuple[str, str]] = [
    ("養育",         "育てる"),
    ("支給され",     "もらえる / お金が入る"),
    ("支給する",     "出す (読者主語なら「もらえる」)"),
    ("受給者",       "もらっている人"),
    ("受給世帯",     "もらっている世帯"),
    ("修業",         "学校に通う"),
    ("就業",         "仕事 / 働くこと"),
    ("償還免除",     "返さなくてよくなる"),
    ("償還",         "返す / 返済"),
    ("貸し付け",     "借りられる (読者を主語にする)"),
    ("給付を受け",   "もらう"),
    ("交付を受け",   "受け取る / もらう"),
    ("自立の促進",   "(制度の目的規定は書かない)"),
    ("生活の安定",   "(制度の目的規定は書かない)"),
    ("に資する",     "(使わない)"),
    ("当該",         "その"),
    ("監護",         "育てている"),
    ("扶養義務者",   "同居している親族"),
    ("認定請求",     "申請"),
    ("失権",         "もらえなくなる"),
    ("資格喪失",     "対象でなくなる"),
    ("生計を同じく", "生活費を一緒にしている"),
    ("被保険者",     "年金 / 保険に入っていた人"),
    ("一部負担金",   "窓口で払うお金"),
    ("実施主体",     "実際に手続きをする窓口"),
    ("支弁",         "支払う"),
    ("措置を講じ",   "(使わない)"),
    ("課税世帯",     "住民税がかかる世帯"),
    ("非課税世帯",   "住民税がかからない世帯"),
    ("併給",         "一緒に受け取れる"),
    ("減免",         "安くなる / 免除される"),
    ("従量料金",     "使った量に応じた料金"),
    ("標準負担額",   "決められた自己負担の額"),
    ("撤廃",         "なくなる"),
    ("世帯構成",     "家族の人数や組み合わせ"),
    ("並びに",       "と / や"),
    ("若しくは",     "または"),
    ("所定の",       "決められた"),
    ("を要する",     "が必要"),
    ("に該当する",   "にあてはまる"),
]

# M19-b: 言い換えると不正確になる語 = 消さずに「初出時にかっこで説明を添える」方式。
#        テキスト中で一度も「語（説明）」の形が出てこなければ INFO で指摘する。
#        (article_title は字数の都合でかっこ説明を置けないため対象外)
GLOSS_TERMS: list[tuple[str, str]] = [
    ("所得",     "所得（収入から必要な分を差し引いた額）"),
    ("控除",     "控除（税金の計算前に差し引ける額）"),
    ("現況届",   "毎年出す届出（現況届）"),
    ("扶養親族", "扶養親族（生活費をみている家族）"),
]

# 素の部分一致だと拾いすぎる語だけ、正規表現で上書きする
#   養育費 = 読者が日常で使う語なので対象外 (養育者・養育する は対象)
#   課税世帯 = 「非課税世帯」の内側で二重に当たるのを防ぐ
BUREAU_TERM_RE = {
    "養育": r"養育(?!費)",
    "課税世帯": r"(?<!非)課税世帯",
}

BUREAU_MASK_RE = [
    re.compile(r"「[^」]*」"),      # 「」内 = 正式名称・原文引用
    re.compile(r"【[^】]*】"),      # 【令和8年度】等
]
# かっこの中身はマスクしない (かっこ内に役所語を隠せてしまうため)。
# 「初出かっこ説明方式」は「役所語の直後が開きかっこ」かどうかで個別に判定する。
OPEN_PAREN = "（("

# M20: 危険語 = 「平易にした結果、正確性を落とした」表現
#
#   M19 (役所語) が「難しすぎる」を検出するのに対し、M20 は**その逆方向の事故**を検出する。
#   実際に 2 度起きている:
#     ① 児童扶養手当を「毎月お金が入る」と書いた (実際は奇数月・年6回)
#     ② 千葉県医療費助成を「自己負担300円まで」と書いた
#        (実際は市町村が定める1回あたりの負担額で、総額の上限ではない)
#
#   ★これらは文脈によっては正しい★ (本当に毎月振り込まれる制度、本当に所得制限がない制度もある)。
#   よって **禁止ではなく「本当に正しいか一次情報で再確認せよ」の合図** とし、CRIT にはしない:
#     - article_title / summary / 見出し … WARN (読者が最初に読む面。補足を置く余地がない)
#     - みさき / 藤井の発言           … INFO (前後で補足できる面なので参考扱い)
#
#   ★藤井 (社労士) の解説も対象に含める★ — M19 は「読みやすさ」の話なので藤井を除外したが、
#   M20 は「正確さ」の話であり、藤井の口から出た誤りは読者にとって最も信じられてしまう。
#   ただし藤井は補足を添えて話す役割なので、吹き出し内は INFO に留める。
#
# (正規表現, なぜ危険か, 安全な言い換え, 同じ文にあれば参考扱い (INFO) に落とす文脈)
DANGER_PATTERNS: list[tuple[str, str, str, str]] = [
    (r"毎月[^。]{0,6}(もらえ|受け取れ|入りま|入る|入り|振り込|支給され|安くな|届きま|もらう)",
     "実際の振込頻度と食い違う (月額で計算される ≠ 毎月振り込まれる)",
     "月額で計算される / 1か月あたりで算定される",
     r"(奇数月|偶数月|年[0-9０-９]{1,2}回|[0-9０-９]{1,2}か月分|まとめて)"),
    (r"最大[0-9０-９][0-9０-９,，.万億]*円[^。]{0,8}(もらえ|受け取れ|支給され|入りま|入る|借りられ|戻って)",
     "全員がその額をもらえるように読める",
     "条件を満たす場合の上限は◯円",
     r"(条件|要件|所得|全部支給|一部支給|場合|人によって|上限)"),
    (r"[0-9０-９][0-9０-９,，]*円まで",
     "総額の上限に見える (実際は 1回・1日など所定の単位あたりのことが多い)",
     "1回・1日など所定の単位で◯円",
     r"(1回|一回|１回|1日|一日|１日|1か月|1ヶ月|1か所|月額|年額|1件|1人|受診|1医療機関|所定|単位)"),
    (r"対象[0-9０-９]+[市町村区]",
     "その市の全域が対象に見える (実際は市内の一部区域だけのことがある)",
     "◯市内の対象区域",
     r"(区域|エリア)"),
    (r"(入学|進学|卒業|就職|就業)(すれ|でき|し)ば[^。]{0,12}(返済不要|返済が?不要|返さなくて|免除)",
     "免除は自動ではなく、期限内の免除申請と認定が必要",
     "入学後に免除申請をして認められた場合",
     ""),
    (r"返済(は|が)?不要",
     "貸付型は免除申請と認定が必要 (給付型なら正しい)",
     "入学後に免除申請をして認められた場合 / 給付なら「返さなくてよいお金」",
     r"(給付|もらえるお金|貸付ではな|返す必要のない)"),
    (r"(当選|抽選|抽せん)[^。]{0,8}[0-9０-９]+倍",
     "実際の当選確率は応募状況で変わる (倍率 = 確率ではない)",
     "抽せん番号が通常の◯倍割り当てられる",
     r"(番号|割り当て|優遇倍率|申込資格)"),
    (r"(申請)?期限は[^。]{0,12}?[0-9０-９]{1,2}[月日]",
     "特別申請・随時受付など、ほかの申請機会を見落とす",
     "通常の申請期限は◯日。ほかの申請機会の有無も確認",
     r"(ほか|他の|随時|特例|例外|も受け付け|場合があ)"),
    (r"無料",
     "自己負担・回数制限などの例外を落としている",
     "◯◯の場合は無料 (要件を添える)",
     r"(要件|条件|場合|以外|除く|一部|自己負担)"),
    (r"全員",
     "対象外になる人が必ずいる (居住・監護・生計同一などの要件)",
     "◯◯を満たす人は全員 (要件を添える)",
     r"(要件|条件|満た|該当|対象となる)"),
    (r"自動(?!車)",
     "多くの制度は申請主義。自動では始まらない",
     "(申請が必要かどうかを明記する)",
     r"(申請|手続|届出|されません|ではありません|わけでは)"),
    (r"(誰|だれ)でも",
     "居住・所得・年齢などの要件がある",
     "(要件を添える)",
     r"(要件|条件|満た|わけでは|ではありません)"),
]

# M21: 制度タイプ別の必須項目 (supports.category から型を判定する)
#      「その型の記事なら必ず触れているはずの論点」に一度も触れていなければ WARN。
#      キーワードの有無しか見ないので、書いてあるかどうかの一次スクリーニングに過ぎない。
CATEGORY_TO_TYPE = {
    "手当": "手当・給付",
    "給付金": "手当・給付",
    "年金": "手当・給付",
    "貸付": "貸付",
    "助成": "医療・減免",
    "税制": "医療・減免",
    "サービス": "サービス・住宅",
}

TYPE_REQUIRED: dict[str, list[tuple[str, str, str]]] = {
    # 型: [(必須項目, 本文に出ていることを確認する正規表現, 書き足すときの観点)]
    "手当・給付": [
        ("算定単位", r"月額|年額|日額|一回限り|1回限り|回限り|1人あたり",
         "月額なのか年額なのか一回限りなのかを明記する"),
        ("実際の振込月", r"奇数月|偶数月|年[0-9０-９]{1,2}回|振込|振り込|支払月|支給月|支払われ",
         "月額で計算されても振込が毎月とは限らない。実際に何月に入るかを書く"),
        ("申請期限", r"申請期限|いつまでに|期限|締切|届出期限|現況届",
         "いつまでに申請すればよいかを書く"),
        ("遡及の可否", r"遡|さかのぼ|過去(の|に)?分|翌月分から",
         "過去にさかのぼって受け取れるのか (原則は申請月の翌月分から等) を書く"),
    ],
    "貸付": [
        ("入金時期", r"入金|振込|振り込|貸付(日|時期)|交付|いつ(お金|資金)?(が|を)?(入る|受け取)",
         "申請してから実際にお金が入るまでの時期を書く"),
        ("審査", r"審査|選考|面談|相談員|決定通知",
         "審査があること・落ちることがあることを書く"),
        ("返済開始", r"返済(の)?開始|据置|据え置き|返済が始ま|償還開始",
         "据置期間が終わって返済が始まる時点を書く"),
        ("返済期間", r"返済期間|償還期間|年以内|回以内|月賦|年賦",
         "何年で返すのかを書く"),
        ("免除手続き", r"免除",
         "免除がある制度なら「申請して認められた場合に限る」ことを書く"),
    ],
    "医療・減免": [
        ("対象外費用", r"対象外|対象になりません|対象となりません|含まれません|適用され(ま)?せん|除きます|除く|自己負担",
         "入院時食事代・差額ベッド代・保険適用外など、対象にならない費用を書く"),
        ("負担額の単位", r"1回|一回|１回|1日|一日|１日|1か月|1ヶ月|1件|1人|1医療機関|受診ごと|月額|1世帯",
         "◯円という数字が「何あたり」の額なのかを書く (総額の上限と誤読させない)"),
        ("事前申請", r"事前|あらかじめ|申請が必要|医療証|受給者証|証の交付|申請しない",
         "先に申請して証をもらう必要があるのかを書く"),
        ("区域差", r"市区町村によって|自治体によって|市町村が定め|お住まいの(市|自治体)|区域|実施していない",
         "自治体・給水区域などで扱いが違うことを書く"),
    ],
    "サービス・住宅": [
        ("実施地域", r"実施していない|実施状況|お住まいの(市|自治体)|自治体によって|市区町村によって|区域|対象地域",
         "実施していない自治体・対象区域外があることを書く"),
        ("募集・予約時期", r"募集|申込|申し込み|予約|抽選|抽せん|受付|随時",
         "いつ募集・予約できるのかを書く"),
        ("利用上限", r"上限|まで利用|年間|時間まで|回まで|日まで|限度",
         "利用できる回数・時間・期間の上限を書く"),
        ("利用できない場合", r"利用できな|使えな|対象外|できません|お断り|不可|優先順位|落選",
         "頼んでも使えないことがある場合を書く"),
    ],
}

# M22: 記事末尾の構成順 (support-article-writer skill 「記事末尾の構成」)
TAIL_SECTIONS: list[tuple[str, str]] = [
    ("基本情報まとめ", r"基本情報|まとめ"),
    # 「寡婦控除との違い（併用はできません）」のような見出しを拾わないよう、
    # 「併用〜」系の語 + 制度を指す名詞 の両方が要る形にする
    ("併用できる制度",
     r"(併用|併せて使え|あわせて使え|一緒に使え|他にも使え|他に使え)[^#]*(制度|支援|サービス|貸付|手当|給付)"),
    ("よくある質問", r"よくある質問|FAQ|Q&A"),
]
# 4 番目 (公式情報・問い合わせ先) は H2 でも :::pointbox でもよい
TAIL_OFFICIAL_H2 = r"参考リンク|公式|問い合わせ|問合せ|窓口一覧"
TAIL_OFFICIAL_BOX = re.compile(r":::(?:pointbox|warning)\{title=\"[^\"]*(?:問い合わせ|問合せ|公式|参考リンク)[^\"]*\"\}")

PHONE_RE = re.compile(r"0\d{1,4}[-‐−ー]\d{1,4}[-‐−ー]\d{3,4}")
IMG_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")
URL_RE = re.compile(r"https?://[^\s)\"'\]<>、。]+")
# 内部リンク: 全国制度 /support/{id} と地域制度 /{pref}/support/{id} の両方 (editorial-url-rules skill)
INTERNAL_RE = re.compile(r"\]\((?:/([a-z][a-z0-9-]*))?/support/(\d+)\)")
DISCLAIMER_RE = re.compile(r"※本記事は令和([0-9]{1,2})年([0-9]{1,2})月時点")
NUM_TOKEN_RE = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?(?:円|万円|か月|ヶ月|カ月|年|歳|%|％|回|人)")

CATEGORY_WEIGHT = {
    "手当": 20,   # 毎年 4 月に金額改定される
    "年金": 20,
    "給付金": 18,
    "税制": 15,   # 毎年の税制改正
    "貸付": 10,
    "助成": 10,
    "サービス": 5,
}


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def fiscal_reiwa(today: dt.date) -> int:
    """今日が属する年度を令和の年数で返す (4 月始まり)。"""
    fy = today.year if today.month >= 4 else today.year - 1
    return fy - 2018


def reiwa_to_date(r_year: int, month: int) -> dt.date:
    return dt.date(2018 + r_year, month, 1)


def http_status(url: str, timeout: int = 15) -> str:
    """curl で HTTP ステータスを取る。到達不能なら 'ERR:<exit>'。"""
    try:
        p = subprocess.run(
            ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}",
             "-L", "--max-time", str(timeout),
             "-A", "Mozilla/5.0 (compatible; site-maintenance/1.0)",
             url],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        code = (p.stdout or "").strip()
        if p.returncode != 0 and code in ("", "000"):
            return f"ERR:{p.returncode}"
        return code or "ERR:empty"
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def line_of(md_lines: list[str], needle: str) -> int:
    for i, line in enumerate(md_lines, 1):
        if needle in line:
            return i
    return 0


SENT_SEP = re.compile(r"(?<=[。！？!?])")
QUESTION_RE = re.compile(r"(？|\?|ですか|でしょうか|んですか|ますか|かな|ますよね)")
NEGATION_RE = re.compile(r"(ではありません|ではない|わけでは|とは限りません|限りません|ではなく|ありません|しません)")


def sentence_at(line: str, pos: int) -> str:
    """line 中の位置 pos を含む文を返す (句点区切り)。"""
    start = 0
    for m in re.finditer(r"[。！？!?]", line):
        if m.end() > pos:
            break
        start = m.end()
    end = len(line)
    for m in re.finditer(r"[。！？!?]", line):
        if m.end() > pos:
            end = m.end()
            break
    return line[start:end].strip()


def soften(sentence: str, matched: str) -> tuple[str, str]:
    """断定表現の検出を文脈で緩和する。

    戻り値 (severity_hint, note):
      - "" ならそのままの重大度
      - "downgrade" なら INFO に落とす (質問文 / 否定文 / 引用「」の中)
    誤検出を黙って捨てず、INFO として残すことで見落としを防ぐ。
    """
    if QUESTION_RE.search(sentence):
        return "downgrade", "質問文中"
    idx = sentence.find(matched)
    if idx >= 0 and NEGATION_RE.search(sentence[idx + len(matched):idx + len(matched) + 30]):
        return "downgrade", "直後が否定"
    for q in re.finditer(r"「([^」]*)」", sentence):
        if matched in q.group(1):
            return "downgrade", "「」内の引用"
    return "", ""


def mask_protected(text: str, official_names: list[str]) -> str:
    """M19 の誤検出源を伏せ字にする。

    伏せるもの (どれも「役所語だが崩してはいけないもの」):
      - 制度の正式名称 (母子父子寡婦福祉資金貸付金 / 高等職業訓練促進給付金 等)
      - 「」で囲んだ原文引用・正式名称
      - 【令和8年度】等の年度表記
    文字数を変えないよう同じ長さの ○ に置換する。
    ※ かっこの中身は伏せない (かっこ内に役所語を隠せてしまうため)。
    """
    for name in sorted([n for n in official_names if n and len(n) >= 3], key=len, reverse=True):
        text = text.replace(name, "○" * len(name))
    for rx in BUREAU_MASK_RE:
        text = rx.sub(lambda m: "○" * len(m.group(0)), text)
    return text


def bureau_hits(text: str, official_names: list[str]) -> list[tuple[str, str, str]]:
    """役所語の検出。戻り値 [(役所語, 言い換え, 前後の文脈)]。"""
    masked = mask_protected(text, official_names)
    out: list[tuple[str, str, str]] = []
    for term, alt in BUREAU_TERMS:
        for m in re.finditer(BUREAU_TERM_RE.get(term, re.escape(term)), masked):
            # 直後が開きかっこなら「初出かっこ説明方式」として許容
            if text[m.end():m.end() + 1] in OPEN_PAREN and m.end() < len(text):
                continue
            out.append((term, alt, text[max(0, m.start() - 12):m.end() + 12]))
    return out


def gloss_misses(text: str, official_names: list[str]) -> list[tuple[str, str]]:
    """言い換え不可の語 (所得・控除等) が、かっこ説明なしで使われていないか。"""
    masked = mask_protected(text, official_names)
    out: list[tuple[str, str]] = []
    for term, how in GLOSS_TERMS:
        if not re.search(BUREAU_TERM_RE.get(term, re.escape(term)), masked):
            continue
        # 元テキストのどこかに「語（…）」があれば初出説明済みとみなす
        if re.search(re.escape(term) + r"\s*[（(]", text):
            continue
        out.append((term, how))
    return out


def danger_hits(text: str, official_names: list[str]) -> list[tuple[str, str, str, str, str]]:
    """M20 危険語の検出。戻り値 [(ヒット文字列, なぜ危険か, 安全な言い換え, 文, 参考扱いの理由)]。

    参考扱いの理由が空文字でなければ、呼び出し側で 1 段階下の severity にする。
    誤検出を黙って捨てず INFO で残すのは M05 / M06 の soften() と同じ方針。
    """
    masked = mask_protected(text, official_names)
    out: list[tuple[str, str, str, str, str]] = []
    for pat, why, alt, ok_ctx in DANGER_PATTERNS:
        for m in re.finditer(pat, masked):
            sent = sentence_at(text, m.start()) or text.strip()
            note = ""
            hint, soft_note = soften(sent, m.group(0))
            if hint:
                note = soft_note
            elif ok_ctx and re.search(ok_ctx, sent):
                note = "同じ文に条件・単位の補足あり"
            out.append((m.group(0), why, alt, sent, note))
    return out


def required_item_misses(md: str, category: str) -> tuple[str, list[tuple[str, str]]]:
    """M21 制度タイプ別の必須項目もれ。戻り値 (型, [(項目, 書くときの観点)])。"""
    stype = CATEGORY_TO_TYPE.get(category or "")
    if not stype:
        return "", []
    misses = [(item, how) for item, rx, how in TYPE_REQUIRED[stype] if not re.search(rx, md)]
    return stype, misses


def tail_order_issues(md: str) -> list[str]:
    """M22 記事末尾の構成順のずれ。戻り値は指摘文のリスト。"""
    heads = [(m.start(), m.group(1).strip()) for m in re.finditer(r"^##\s+(.+)$", md, re.M)]
    issues: list[str] = []
    found: list[tuple[int, str, str]] = []   # (出現順, 節名, 実際の見出し)
    for name, rx in TAIL_SECTIONS:
        hit = next(((i, h) for i, (_p, h) in enumerate(heads) if re.search(rx, h)), None)
        if hit is None:
            issues.append(f"「{name}」に相当する H2 が無い")
        else:
            found.append((hit[0], name, hit[1]))
    if len(found) >= 2:
        ordered = sorted(found, key=lambda x: x[0])
        if [f[1] for f in ordered] != [f[1] for f in found]:
            issues.append("順序が 基本情報まとめ → 併用できる制度 → よくある質問 になっていない "
                          "(現状: " + " → ".join(f"「{f[2]}」" for f in ordered) + ")")
    has_official = any(re.search(TAIL_OFFICIAL_H2, h) for _p, h in heads) or bool(TAIL_OFFICIAL_BOX.search(md))
    if not has_official:
        issues.append("「公式情報・問い合わせ先」が無い "
                      "(H2 も :::pointbox{title=\"問い合わせ先\"} も見当たらない)")
    return issues


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------

def check_article(rec: dict, ctx: dict) -> dict:
    """1 記事分のチェック。findings のリストを返す。"""
    md = rec.get("article_md") or ""
    lines = md.split("\n")
    today: dt.date = ctx["today"]
    net: bool = ctx["net"]
    status_cache: dict = ctx["status_cache"]
    findings: list[dict] = []
    manual: list[str] = []      # 目視・一次情報照合キュー

    def add(code: str, sev: str, msg: str, line: int = 0):
        findings.append({"code": code, "severity": sev, "line": line, "message": msg})

    # ---- M01 official_url / source_url ----
    if net:
        for col in ("official_url", "source_url"):
            u = rec.get(col)
            if not u:
                if col == "official_url":
                    add("M01", WARN, "official_url が DB に未設定")
                continue
            code = status_cache.get(u, "")
            if code.startswith("ERR") or code in ("404", "410", "0", "000"):
                add("M01", CRIT, f"{col} が到達不能 [{code}] {u}")
            elif code.startswith("5") or code == "403":
                add("M01", WARN, f"{col} が HTTP {code} (要目視) {u}")

    # ---- M02 本文中の外部 URL ----
    body_urls = sorted({u.rstrip(".,)") for u in URL_RE.findall(md)})
    img_urls = [u for _, u in IMG_RE.findall(md)]
    if net:
        for u in body_urls:
            if u in img_urls:
                continue
            code = status_cache.get(u, "")
            if code.startswith("ERR") or code in ("404", "410", "0", "000"):
                add("M02", CRIT, f"本文リンク切れ [{code}] {u}", line_of(lines, u))
            elif code.startswith("5") or code == "403":
                add("M02", WARN, f"本文リンクが HTTP {code} (要目視) {u}", line_of(lines, u))

    # ---- M03 図解画像 URL ----
    if len(img_urls) < 2:
        add("M03", CRIT, f"図解画像が {len(img_urls)} 枚 (2 枚未満)")
    if net:
        for u in img_urls:
            code = status_cache.get(u, "")
            if code != "200":
                add("M03", CRIT, f"画像配信 [{code}] {u}")

    # ---- M04 内部リンク (実在性 + editorial-url-rules の全国/地域パス整合) ----
    for pref, sid_s in sorted(set(INTERNAL_RE.findall(md))):
        sid = int(sid_s)
        path = f"/{pref}/support/{sid}" if pref else f"/support/{sid}"
        target = ctx["by_id"].get(sid)
        if target is None:
            add("M04", CRIT, f"内部リンク先 {path} が DB に存在しない", line_of(lines, path))
            continue
        if target.get("status") != "active":
            add("M04", CRIT, f"内部リンク先 {path} が status={target.get('status')}", line_of(lines, path))
        if not (target.get("article_md") or ""):
            add("M04", WARN, f"内部リンク先 {path} は記事未執筆 (空ページ)", line_of(lines, path))
        # 全国制度 = /support/{id} / 地域制度 = /{pref}/support/{id}
        nationwide = bool(target.get("is_nationwide"))
        slugs = ctx["pref_slugs"].get(sid, [])
        if nationwide and pref:
            add("M04", CRIT, f"全国制度を地域パスでリンク ({path} は 404)。正: /support/{sid}", line_of(lines, path))
        elif not nationwide and not pref:
            add("M04", WARN, f"地域制度を全国パスでリンク ({path} は 308 リダイレクト)。正: /{slugs[0] if slugs else '{pref}'}/support/{sid}",
                line_of(lines, path))
        elif not nationwide and pref and slugs and pref not in slugs:
            add("M04", CRIT, f"地域制度の都道府県 slug 不一致 ({path})。DB 上の slug: {slugs}", line_of(lines, path))

    # ---- M05 対象者の断定 ----
    for i, line in enumerate(lines, 1):
        for pat, label in ASSERTION_PATTERNS:
            for mm in re.finditer(pat, line):
                sent = sentence_at(line, mm.start())
                hint, note = soften(sent, mm.group(0))
                sev = INFO if hint else CRIT
                suffix = f" ※{note}のため参考扱い" if note else ""
                add("M05", sev, f"{label}「{mm.group(0)}」: {sent[:80]}{suffix}", i)

    # ---- M06 根拠なし全国傾向 ----
    for i, line in enumerate(lines, 1):
        for pat in NATIONWIDE_PATTERNS:
            for mm in re.finditer(pat, line):
                sent = sentence_at(line, mm.start())
                hint, note = soften(sent, mm.group(0))
                # ★この緩和は M06 だけ★ soften() は他の検出とも共用なので、
                #   ここで足す (共用側に入れると M20 等の件数まで動いてしまう)
                if not hint and EVIDENCE_RE.search(sent):
                    hint, note = "downgrade", "同じ文に具体例・出典あり"
                sev = INFO if hint else WARN
                suffix = f" ※{note}のため参考扱い" if note else ""
                add("M06", sev, f"根拠なし全国傾向表現の疑い「{mm.group(0)}」: {sent[:80]}{suffix}", i)

    # ---- M07 免責注意書きの時点 ----
    m = DISCLAIMER_RE.search(md)
    if not m:
        if "※本記事は" not in md or "市区町村" not in md:
            add("M07", CRIT, "記事末尾の免責注意書きが見つからない")
        else:
            add("M07", WARN, "免責注意書きに「令和X年M月時点」の時点表記がない")
    else:
        stated = reiwa_to_date(int(m.group(1)), int(m.group(2)))
        months = (today.year - stated.year) * 12 + (today.month - stated.month)
        if months >= 12:
            add("M07", CRIT, f"免責の時点が {months} か月前 (令和{m.group(1)}年{m.group(2)}月時点) — 内容を再検証して時点を更新")
        elif months >= 6:
            add("M07", WARN, f"免責の時点が {months} か月前 (令和{m.group(1)}年{m.group(2)}月時点)")

    # ---- M08 updated_at 経過 ----
    upd = rec.get("updated_at")
    days = None
    if upd:
        try:
            d = dt.datetime.fromisoformat(upd.replace("Z", "+00:00")).date()
            days = (today - d).days
            if days >= 365:
                add("M08", CRIT, f"最終更新から {days} 日 (1 年以上)")
            elif days >= 180:
                add("M08", WARN, f"最終更新から {days} 日 (半年以上)")
        except ValueError:
            add("M08", WARN, f"updated_at をパースできない: {upd}")

    # ---- M09 年度リテラル ----
    cur_fy = ctx["cur_fy"]
    years = {int(x) for x in re.findall(r"令和([0-9]{1,2})年度", md)}
    for y in sorted(years):
        if y < cur_fy:
            add("M09", WARN, f"旧年度表記 令和{y}年度 が残存 (現年度=令和{cur_fy}年度)。改定の有無を一次情報で確認",
                line_of(lines, f"令和{y}年度"))
        elif y > cur_fy + 1:
            add("M09", WARN, f"未来年度 令和{y}年度 に言及 (公式資料に実在するか一次情報で確認。記事11 の「令和9年4月申請分まで」型の事故)",
                line_of(lines, f"令和{y}年度"))

    # ---- M10 reviewer_verifications ----
    rn = rec.get("research_notes") or {}
    if not isinstance(rn, dict):
        rn = {}
    rv = rn.get("reviewer_verifications") or []
    if not rv:
        add("M10", WARN, "research_notes.reviewer_verifications が無い (公開前査読の記録なし)")
    else:
        last = max((v.get("verified_at", "") for v in rv if isinstance(v, dict)), default="")
        if last:
            try:
                d = dt.datetime.fromisoformat(last.replace("Z", "+00:00")).date()
                gap = (today - d).days
                if gap >= 365:
                    add("M10", WARN, f"最終査読から {gap} 日 (1 年以上)")
            except ValueError:
                pass
    srcs = rn.get("sources") or []
    if len(srcs) < 3:
        add("M10", WARN, f"research_notes.sources が {len(srcs)} 件 (3 件未満)")

    # ---- M11 前回メンテ点検 ----
    mc = rn.get("maintenance_checks") or []
    last_maint = max((v.get("checked_at", "") for v in mc if isinstance(v, dict)), default="")
    if not last_maint:
        add("M11", INFO, "メンテナンス点検の記録がまだ無い (今回が初回)")
    else:
        try:
            d = dt.datetime.fromisoformat(last_maint.replace("Z", "+00:00")).date()
            gap = (today - d).days
            if gap >= 180:
                add("M11", WARN, f"前回のメンテナンス点検から {gap} 日")
        except ValueError:
            pass

    # ---- M12 amount_max と本文金額 ----
    amax = rec.get("amount_max")
    if amax:
        amax = int(amax)
        variants = {f"{amax:,}", str(amax)}
        if amax % 10000 == 0:
            variants.add(f"{amax // 10000:,}万")
        if not any(v in md for v in variants):
            add("M12", WARN, f"DB の amount_max ({amax:,}円) が本文に見当たらない (改定 or DB 側が古い可能性)")

    # ---- M13 表示崩れ・AI 臭 ----
    for i, line in enumerate(lines, 1):
        if "：" in line and not line.strip().startswith("|"):
            add("M13", CRIT, f"全角コロン: {line.strip()[:60]}", i)
        if re.search(r"(?<!\d)\d{1,2}:\d{2}(?!\d|分|秒|\.)", line) and "|" not in line and "http" not in line:
            add("M13", CRIT, f"HH:MM 形式 (ディレクティブ誤認): {line.strip()[:60]}", i)
        if "<mark>" in line and "</mark>" not in line:
            add("M13", CRIT, "mark タグ未閉じ", i)
    opens = sum(1 for l in lines if l.strip().startswith(":::") and len(l.strip()) > 3)
    closes = sum(1 for l in lines if l.strip() == ":::")
    if opens != closes:
        add("M13", CRIT, f"ディレクティブ開閉不一致 (open={opens}, close={closes})")
    if "<!-- FAQ_JSON" not in md:
        add("M13", CRIT, "FAQ_JSON が見つからない")
    for ph in AI_PHRASES:
        if ph in md:
            add("M13", WARN, f"AI 臭フレーズ: 「{ph}」", line_of(lines, ph))

    # ---- M14 図解画像の目視キュー ----
    if img_urls:
        add("M14", INFO, f"図解画像 {len(img_urls)} 枚は機械判定不能。--images で DL し Read で 1 枚ずつ目視 (reviewer skill 10c/E15 と同一基準)")
        for n, (alt, u) in enumerate(IMG_RE.findall(md), 1):
            manual.append(f"[画像{n}] alt=「{alt[:60]}」 {u}")

    # ---- M18 画像の他記事との混線 ----
    #      画像の「中身」は判定できないが、命名規約 ({id}-*.png) と使い回しは機械で拾える。
    #      26 枚中 10 枚が別制度の画像だった事故の、唯一の自動検出層。
    for u in img_urls:
        fname = u.rsplit("/", 1)[-1].split("?")[0]
        if not re.match(rf"^{rec['id']}-", fname):
            add("M18", WARN, f"画像ファイル名が命名規約 ({rec['id']}-*) に合わない: {fname} (他記事の画像の流用を疑う)")
        others = [oid for oid, urls in ctx["img_owner"].items() if oid != rec["id"] and u in urls]
        if others:
            add("M18", CRIT, f"同じ画像 URL を記事 {others} と共有: {fname} (どちらかの制度と中身が食い違う)")

    # ---- M15 alt と本文の数値不一致 ----
    for n, (alt, u) in enumerate(IMG_RE.findall(md), 1):
        alt_nums = {t for t in NUM_TOKEN_RE.findall(alt)}
        body = md.replace(alt, "")
        missing = [t for t in sorted(alt_nums) if t not in body]
        if missing:
            add("M15", WARN,
                f"画像{n} の alt にある数値 {missing} が本文に存在しない (図を直して alt が旧のまま、の疑い) alt=「{alt[:50]}」")

    # ---- M16 時期・回数・期限の断定 ----
    hits: list[str] = []
    seen_sched: set[tuple[int, str]] = set()
    for i, line in enumerate(lines, 1):
        for pat in SCHEDULE_PATTERNS:
            for mm in re.finditer(pat, line):
                key = (i, mm.group(0))
                if key in seen_sched:
                    continue
                seen_sched.add(key)
                hits.append(f"L{i} 「{mm.group(0)}」 … {sentence_at(line, mm.start())[:70]}")
    if hits:
        add("M16", INFO, f"時期・回数・期限の断定 {len(hits)} 箇所。公式ページで年間スケジュールを再確認 (記事13「年2回の定期募集」型の事故)")
        manual.extend(f"[時期] {h}" for h in hits[:20])

    # ---- M19 役所言葉の残存 ----
    #      読者が最初に読む面 (タイトル / カード説明文 = meta description / みさきの発言 / 見出し)
    #      から役所語を排除する。★藤井 (社労士) の解説は制度用語を使ってよいので対象外★
    #      support-article-writer skill 「読者の言葉で書くルール」/ reviewer E20 と同一の語彙表。
    official_names = [r.get("title") for r in ctx["by_id"].values()]
    official_names += [rec.get("title")]

    for term, alt, ctxt in bureau_hits(rec.get("article_title") or "", official_names):
        add("M19", WARN, f"article_title に役所語「{term}」→「{alt}」に。…{ctxt}…")
    for term, alt, ctxt in bureau_hits(rec.get("summary") or "", official_names):
        add("M19", WARN, f"summary に役所語「{term}」→「{alt}」に。…{ctxt}…")
    for term, how in gloss_misses(rec.get("summary") or "", official_names):
        add("M19", INFO, f"summary の「{term}」にかっこ説明がない (言い換え不可の語は初出でかっこ補足)。例: {how}")

    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("**藤井**:"):
            continue  # ★藤井の解説は制度用語 OK (役割上むしろ正確であるべき)★
        if s.startswith("**みさき**:"):
            where = "みさきの発言"
        elif s.startswith("#"):
            where = "見出し"
        else:
            continue
        for term, alt, ctxt in bureau_hits(s, official_names):
            add("M19", WARN, f"{where}に役所語「{term}」→「{alt}」に。…{ctxt}…", i)

    # ---- M17 電話番号 ----
    phones = sorted(set(PHONE_RE.findall(md)))
    if phones:
        add("M17", INFO, f"電話番号 {len(phones)} 件。外部指摘があっても必ず公式ページの現行番号で照合 (記事13 の実例: 指摘の方が誤りだった)")
        manual.extend(f"[電話] {p}" for p in phones)

    # ---- M20 危険語 (平易化のときに正確性を落とす表現) ----
    #      「本当に正しいか一次情報で再確認せよ」の合図。★禁止ではない★ ので CRIT にしない。
    #      ★M19 と違い藤井の解説も対象★ — M19 は読みやすさ、M20 は正確さの話であり、
    #      藤井 (社労士) の口から出た誤りこそ読者に信じられてしまうため。
    #      ただし吹き出し内は前後で補足できるので INFO、補足を置けない 3 面のみ WARN。
    #
    #      誤検出の扱いが面によって違う:
    #        - article_title / summary / 見出し … 質問文・否定・単位の補足があれば INFO に落とす
    #          (捨てない。読者が最初に読む面なので見落としのほうが高くつく)
    #        - みさき / 藤井の発言 … 上記の補足があるものは出さない
    #          (吹き出しは「自動的に支給されるものではなく…」のように打ち消して書くのが正しい形。
    #           これを全部出すとレポートが読めなくなり、本当に危ない 1 件が埋もれる)
    def add_danger(where: str, text: str, base_sev: str, line: int = 0):
        for hit, why, alt, sent, note in danger_hits(text, official_names):
            if note and base_sev == INFO:
                continue
            sev = INFO if (note or base_sev == INFO) else WARN
            suffix = f" ※{note}のため参考扱い" if note else ""
            add("M20", sev,
                f"{where}に危険語「{hit}」({why})。安全な言い換え: {alt} — {sent[:70]}{suffix}", line)

    add_danger("article_title", rec.get("article_title") or "", WARN)
    add_danger("summary", rec.get("summary") or "", WARN)
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            add_danger("見出し", s, WARN, i)
        elif s.startswith("**みさき**:"):
            add_danger("みさきの発言", s, INFO, i)
        elif s.startswith("**藤井**:"):
            add_danger("藤井の解説", s, INFO, i)

    # ---- M21 制度タイプ別の必須項目もれ ----
    stype, misses = required_item_misses(md, rec.get("category") or "")
    if stype:
        for item, how in misses:
            add("M21", WARN, f"{stype}型の必須項目「{item}」に本文が一度も触れていない疑い。{how}")
    elif rec.get("category"):
        add("M21", INFO, f"category「{rec.get('category')}」が制度タイプ表に無い (CATEGORY_TO_TYPE に追加を検討)")

    # ---- M22 記事末尾の構成順 ----
    #      既存記事の作り直しは今回の対象外 (新規記事から適用) なので INFO に留める。
    for issue in tail_order_issues(md):
        add("M22", INFO, f"記事末尾の構成: {issue}")

    # ---- 優先度スコア ----
    n_crit = sum(1 for f in findings if f["severity"] == CRIT)
    n_warn = sum(1 for f in findings if f["severity"] == WARN)
    inbound = ctx["inbound"].get(rec["id"], 0)
    score = (
        inbound * 10
        + CATEGORY_WEIGHT.get(rec.get("category") or "", 8)
        + (min(days, 730) / 30 * 5 if days else 0)
        + n_crit * 30
        + n_warn * 5
    )

    return {
        "id": rec["id"],
        "title": rec.get("title"),
        "category": rec.get("category"),
        "updated_at": upd,
        "days_since_update": days,
        "inbound_links": inbound,
        "images": img_urls,
        "priority_score": round(score, 1),
        "counts": {"CRIT": n_crit, "WARN": n_warn,
                   "INFO": sum(1 for f in findings if f["severity"] == INFO)},
        "findings": findings,
        "manual_queue": manual,
    }


def download_images(result: dict, out_root: str) -> list[str]:
    d = os.path.join(out_root, str(result["id"]))
    os.makedirs(d, exist_ok=True)
    paths = []
    for n, u in enumerate(result["images"], 1):
        p = os.path.join(d, f"{n:02d}-{u.rsplit('/', 1)[-1].split('?')[0]}")
        subprocess.run(["curl", "-s", "-L", "--max-time", "60", "-o", p, u],
                       capture_output=True, timeout=90)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            paths.append(os.path.abspath(p))
        else:
            result["findings"].append({"code": "M14", "severity": CRIT, "line": 0,
                                       "message": f"画像 DL 失敗: {u}"})
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description="公開済み記事の定期点検 (機械チェック層)")
    ap.add_argument("json_path", help="supports の SELECT 結果 JSON (article-health-check.sh が生成)")
    ap.add_argument("--id", type=int, action="append", help="対象記事 ID (複数可)。省略時は article_md がある全記事")
    ap.add_argument("--quick", action="store_true", help="ネットワークチェック (M01/M02/M03) を省略")
    ap.add_argument("--images", action="store_true", help="図解画像を DL して目視キューにローカルパスを出す")
    ap.add_argument("--out-dir", default=".scratch/maintenance", help="画像 DL 先 (既定: .scratch/maintenance)")
    ap.add_argument("--json", dest="json_out", help="結果を JSON で書き出すパス")
    ap.add_argument("--today", help="基準日 YYYY-MM-DD (既定: 今日)")
    args = ap.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        rows = json.load(f)
    if isinstance(rows, dict):
        print(f"[health-check] Supabase からエラー応答: {rows}", file=sys.stderr)
        return 2

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    by_id = {r["id"]: r for r in rows}

    # 内部被リンク数 (アクセス数の代理指標): 他記事から /support/{id} で参照された回数
    inbound: dict[int, int] = {}
    for r in rows:
        for _pref, sid_s in set(INTERNAL_RE.findall(r.get("article_md") or "")):
            sid = int(sid_s)
            if sid != r["id"]:
                inbound[sid] = inbound.get(sid, 0) + 1

    # 地域制度の都道府県 slug (editorial-url-rules のパス整合チェック用)
    pref_slugs: dict[int, list[str]] = {}
    for r in rows:
        slugs = []
        for sp in (r.get("support_prefectures") or []):
            p = (sp or {}).get("prefectures") or {}
            if p.get("slug"):
                slugs.append(p["slug"])
        pref_slugs[r["id"]] = slugs

    targets = [r for r in rows if (r.get("article_md") or "")]
    if args.id:
        targets = [r for r in targets if r["id"] in set(args.id)]
    if not targets:
        print("[health-check] 対象記事がありません", file=sys.stderr)
        return 1

    # URL 到達性はまとめて並列取得 (記事をまたいで重複排除)
    status_cache: dict[str, str] = {}
    if not args.quick:
        urls: set[str] = set()
        for r in targets:
            md = r.get("article_md") or ""
            urls |= {u.rstrip(".,)") for u in URL_RE.findall(md)}
            for col in ("official_url", "source_url"):
                if r.get(col):
                    urls.add(r[col])
        urls = {u for u in urls if u.startswith("http")}
        print(f"[health-check] URL 到達性チェック {len(urls)} 件 (重複排除済み) ...", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=8) as ex:
            for u, code in zip(urls, ex.map(http_status, urls)):
                status_cache[u] = code

    ctx = {
        "today": today,
        "cur_fy": fiscal_reiwa(today),
        "net": not args.quick,
        "status_cache": status_cache,
        "by_id": by_id,
        "inbound": inbound,
        "pref_slugs": pref_slugs,
        "img_owner": {r["id"]: [u for _a, u in IMG_RE.findall(r.get("article_md") or "")] for r in rows},
    }

    results = [check_article(r, ctx) for r in targets]
    if args.images:
        digests: dict[str, list[str]] = {}
        for res in results:
            paths = download_images(res, args.out_dir)
            res["image_paths"] = paths
            for p in paths:
                import hashlib
                with open(p, "rb") as fh:
                    h = hashlib.md5(fh.read()).hexdigest()
                digests.setdefault(h, []).append(f"{res['id']}:{os.path.basename(p)}")
        for h, owners in digests.items():
            if len(owners) > 1 and len({o.split(":")[0] for o in owners}) > 1:
                for res in results:
                    if any(o.startswith(f"{res['id']}:") for o in owners):
                        res["findings"].append({
                            "code": "M18", "severity": CRIT, "line": 0,
                            "message": f"画像バイナリが他記事と同一 (md5={h[:8]}): {owners} — 中身がどちらかの制度と食い違う",
                        })
                        res["counts"]["CRIT"] += 1

    results.sort(key=lambda r: -r["priority_score"])

    # ---- レポート出力 ----
    tot = {"CRIT": 0, "WARN": 0, "INFO": 0}
    for r in results:
        for k in tot:
            tot[k] += r["counts"][k]

    print("=" * 72)
    print(f"公開済み記事 定期点検レポート  基準日 {today} (令和{ctx['cur_fy']}年度)")
    print(f"対象 {len(results)} 記事 / CRIT {tot['CRIT']} · WARN {tot['WARN']} · INFO {tot['INFO']}"
          + ("  ※--quick のため URL 到達性は未検査" if args.quick else ""))
    if status_cache:
        dist: dict[str, int] = {}
        for c in status_cache.values():
            dist[c] = dist.get(c, 0) + 1
        print("URL 到達性: " + " / ".join(f"{k}×{v}" for k, v in sorted(dist.items())))
    print("=" * 72)

    print("\n## 優先度ランキング (上から着手する)")
    print(f"{'順':>2} {'ID':>3} {'score':>7} {'CRIT':>4} {'WARN':>4} {'被link':>6} {'経過日':>6}  タイトル")
    for i, r in enumerate(results, 1):
        print(f"{i:>2} {r['id']:>3} {r['priority_score']:>7} {r['counts']['CRIT']:>4} "
              f"{r['counts']['WARN']:>4} {r['inbound_links']:>6} "
              f"{(r['days_since_update'] if r['days_since_update'] is not None else -1):>6}  {r['title']}")

    for r in results:
        if not r["findings"]:
            continue
        print("\n" + "-" * 72)
        print(f"### [{r['id']}] {r['title']}  (score {r['priority_score']}, "
              f"CRIT {r['counts']['CRIT']} / WARN {r['counts']['WARN']})")
        for sev in (CRIT, WARN, INFO):
            for f in r["findings"]:
                if f["severity"] != sev:
                    continue
                loc = f" L{f['line']}" if f["line"] else ""
                print(f"  [{sev}] {f['code']}{loc}: {f['message']}")
        if r.get("image_paths"):
            print("  ★目視必須 (Read ツールで 1 枚ずつ開く。HTTP 200 は合格の根拠にならない)★")
            for p in r["image_paths"]:
                print(f"    Read {p}")
        if r["manual_queue"]:
            print("  --- 一次情報照合キュー ---")
            for q in r["manual_queue"]:
                print(f"    {q}")

    print("\n" + "=" * 72)
    print("機械で判定できないもの (必ず人 or AI が一次情報で確認する):")
    print("  1. 図解画像の中身が記事の制度と一致しているか            → M14 (--images + Read)")
    print("  2. 図の数値が本文の表と一致しているか                    → M14 (本文と突き合わせ)")
    print("  3. 制度の内容そのものが現行と一致しているか              → M16 の照合キュー + official_url を WebFetch")
    print("  4. 記事にある期限・回数が公式資料に実在するか            → M09/M16 の照合キュー")
    print("  5. 外部レビュー (GPT 等) の指摘自体が正しいか            → 指摘は必ず一次情報で検証してから直す")
    print("=" * 72)

    if args.json_out:
        payload = {
            "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "basis_date": today.isoformat(),
            "mode": "quick" if args.quick else "full",
            "totals": tot,
            "articles": results,
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n[health-check] JSON 出力: {os.path.abspath(args.json_out)}")

    return 1 if tot["CRIT"] else 0


if __name__ == "__main__":
    sys.exit(main())
