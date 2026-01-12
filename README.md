# Discord翻訳Bot（中国語繁体字 ↔ 韓国語）

Discordサーバーでリアルタイムにテキストを翻訳するBotです。

## 主な機能

- **自動翻訳**: 中国語繁体字 ↔ 韓国語を自動翻訳
- **自動言語検出**: 入力されたテキストの言語を自動判定
- **日本語・英語翻訳ボタン**: 翻訳結果に日本語・英語翻訳ボタンを表示
- **DeepL + Google翻訳フォールバック**: DeepL APIエラー時はGoogle翻訳に切り替え

## 翻訳動作

| 入力言語 | 自動翻訳先 | ボタン翻訳 |
|----------|------------|------------|
| 中国語繁体字 | 韓国語 | 日本語・英語 |
| 韓国語 | 中国語繁体字 | 日本語・英語 |
| その他 | 韓国語 | 日本語・英語 |

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `DISCORD_TOKEN` | Yes | Discord Botのトークン |
| `DEEPL_TOKEN` | Yes | DeepL APIキー |
| `DISCORD_CHANNEL_ID` | No | 特定チャンネルのみで動作させる場合に指定 |
| `EXCLUDED_CHANNEL_IDS` | No | 翻訳を除外するチャンネルID（カンマ区切り） |

## プロジェクト構造

```
├── neo-bot.py         # メインのBotファイル
├── requirements.txt   # Python依存関係
├── Procfile           # Koyebデプロイ設定
├── runtime.txt        # Pythonバージョン指定
└── pyproject.toml     # Python設定
```

## デプロイ

**Koyeb** (https://app.koyeb.com/) でホスティング

- mainブランチへのマージで自動デプロイ
- Flaskサーバーがポート8080で起動（Keep-alive用）

## Botコマンド

- `!help` / `!ヘルプ` - ヘルプを表示
- `おやすみttt` - Bot停止（管理者のみ）

## 使用技術

- Python 3.11
- discord.py - Discord Bot開発ライブラリ
- DeepL API - 高品質翻訳
- googletrans - フォールバック翻訳
- langdetect - 言語自動検出
- Flask - Keep-aliveサーバー
