# マイナビ交通費サーチ PWA

GitHub Actions上でマイナビ2028の公開検索一覧を差分巡回し、交通費・宿泊費・開催日・開催地をiPhoneから検索できるPWAです。

## 巡回の役割分担

| ジョブ | 頻度 | 処理 |
|---|---:|---|
| Discover new internships | 30分ごと | 検索一覧を巡回し、新規の企業ID＋コースIDを発見。その実行内で新規募集の詳細を取得 |
| Refresh existing internships | 6時間ごと | 既存募集を古い確認順に分散再確認し、交通費・日程・締切などの変更を更新 |
| Check urgent deadlines | 1時間ごと | 締切が3日以内の掲載中募集だけを再確認 |
| Clean up closed internships | 1日1回（日本時間3時台） | 終了・満席・中止候補を再確認し、状態を更新。履歴は削除しない |

GitHub ActionsのcronはUTCです。実行は混雑により多少遅れることがあります。

## 重複排除

1. 企業ID＋コースID
2. 追跡パラメータを除いた正規化URL
3. 企業名＋コース名＋開催日＋開催地の内容指紋

同一コースが複数の検索カテゴリや一覧ページに出ても1件に統合します。

## 主な機能

- 交通費の最低金額、全額・実費、宿泊費で絞り込み
- 開催日を単日または期間で指定
- 終了・満席は初期状態で非表示（必要時に表示可能）
- お気に入りをiPhone内に保存
- ホーム画面へ追加してアプリとして利用

## 公開方法

1. フォルダの中身をGitHubリポジトリへアップロード
2. Settings → Pages → Source を `GitHub Actions` に設定
3. Actionsの `Discover new internships` を手動実行
4. Pages URLをiPhoneのSafariで開き、「ホーム画面に追加」

`targets.txt`へ個別コースURLを追加すると、全体巡回とは別に優先登録できます。
