# assets/fonts/ — テキスト焼き込み用フォント（任意）

リールのスライドテキスト（headline / sub_text）は `overlay_text.py` がPILで描画します。
このフォルダは**空のままで動きます**（macOS標準のヒラギノ角ゴシックに自動フォールバック）。

## フォントを差し替えたい場合

`.ttf` / `.otf` ファイルをこのフォルダに置くだけで最優先で使われます。

- ファイル名に **`bold`**（見出し用）/ **`medium`**（本文用）を含めると、
  太さの割り当てが正しく行われます（例: `NotoSansJP-Bold.otf` / `NotoSansJP-Medium.otf`）
- おすすめは [Noto Sans JP](https://fonts.google.com/noto/specimen/Noto+Sans+JP)
  （Google製・SIL Open Font Licenseで無料・再配布可）

## 注意（ライセンス）

游ゴシック・ヒラギノなど**OS付属フォントのファイルコピーを配布物に含めるのはライセンス違反**です。
自分のMac上でパイプラインが使うぶんには問題ありません（このフォルダに置かず、
フォールバックに任せてください）。
