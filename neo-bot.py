import discord
from discord.ui import View, Button
import requests
import os
import sys
import asyncio
import gc
import psutil
from datetime import datetime
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from flask import Flask, jsonify
from threading import Thread
from googletrans import Translator

# 環境変数からトークンを取得（セキュリティ向上）
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DEEPL_TOKEN = os.getenv('DEEPL_TOKEN')
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')  # 環境変数から取得（オプション）
EXCLUDED_CHANNEL_IDS = os.getenv('EXCLUDED_CHANNEL_IDS', '')  # 除外チャンネルID（カンマ区切り）

# トークンの存在確認
if not DISCORD_TOKEN or not DEEPL_TOKEN:
    print("エラー: 環境変数DISCORD_TOKEN, DEEPL_TOKENを設定してください")
    exit()

# チャンネルIDはオプション（全チャンネル対応のため）
if DISCORD_CHANNEL_ID:
    DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID)
    print(f"🎯 指定チャンネル（{DISCORD_CHANNEL_ID}）でのみ動作します")
else:
    print("🌍 全チャンネルで動作します")

# 除外チャンネルIDの処理
excluded_channels = set()
if EXCLUDED_CHANNEL_IDS.strip():
    try:
        excluded_channels = {int(ch_id.strip()) for ch_id in EXCLUDED_CHANNEL_IDS.split(',') if ch_id.strip()}
        print(f"🚫 除外チャンネル: {excluded_channels}")
    except ValueError:
        print("⚠️ 除外チャンネルIDの形式が正しくありません")
        excluded_channels = set()

# Discord設定
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# フォールバック翻訳器（GoogleTranslate）
google_translator = Translator()

# Keep-Alive機能（Flaskサーバー）
app = Flask('')

@app.route('/')
def health_check():
    """ヘルスチェック用エンドポイント"""
    # メモリ使用量を取得
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    
    return jsonify({
        "status": "ok",
        "message": "Discord Bot is running",
        "python_version": sys.version,
        "timestamp": datetime.now().isoformat(),
        "discord_bot_status": "connected" if client.is_ready() else "connecting",
        "memory_usage_mb": round(memory_mb, 2),
        "memory_percent": round(psutil.virtual_memory().percent, 2)
    })

@app.route('/health')
def health():
    """追加のヘルスチェックエンドポイント"""
    return jsonify({
        "status": "healthy",
        "uptime": datetime.now().isoformat(),
        "bot_ready": client.is_ready()
    })

@app.route('/ping')
def ping():
    """シンプルなpingエンドポイント（スリープ防止用）"""
    return "pong"

@app.route('/keepalive')
def keepalive():
    """Keep-alive専用エンドポイント"""
    return jsonify({"alive": True, "timestamp": datetime.now().isoformat()})

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

async def periodic_health_check():
    """4分ごとにセルフヘルスチェックとメモリ管理を実行（スリープ防止）"""
    while True:
        try:
            await asyncio.sleep(240)  # 4分待機（5分制限より短く）
            
            # メモリ使用量チェック
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            port = int(os.environ.get('PORT', 8080))
            # 複数のエンドポイントでヘルスチェック
            endpoints = [f'http://localhost:{port}/', f'http://localhost:{port}/ping', f'http://localhost:{port}/keepalive']
            success = False
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code == 200:
                        success = True
                        break
                except:
                    continue
            
            if not success:
                response = requests.get(f'http://localhost:{port}/', timeout=10)
            
            if response.status_code == 200:
                print(f"✅ ヘルスチェック成功 (メモリ: {memory_mb:.1f}MB)")
                
                # メモリが400MB超過時にガベージコレクション実行
                if memory_mb > 400:
                    print("🧹 メモリクリーンアップ実行中...")
                    gc.collect()
                    new_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    print(f"🧹 クリーンアップ完了: {memory_mb:.1f}MB → {new_memory:.1f}MB")
                    
            else:
                print(f"⚠️ ヘルスチェック警告: ステータスコード {response.status_code}")
                
        except Exception as e:
            print(f"❌ ヘルスチェックエラー: {e}")

def keep_alive():
    """Webサーバーを別スレッドで起動してbotを生存させる"""
    server = Thread(target=run_flask)
    server.daemon = True
    server.start()
    port = int(os.environ.get('PORT', 8080))
    print(f"🌐 Keep-aliveサーバーがポート{port}で起動しました")
    print("🔄 4分ごとのヘルスチェックを開始します（スリープ防止）")

# DeepL API設定
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

# DeepLがサポートする言語コードのマッピング
DEEPL_SUPPORTED_LANGS = {
    'ja': 'ja',
    'en': 'en', 
    'de': 'de',
    'fr': 'fr',
    'es': 'es',
    'pt': 'pt',
    'it': 'it',
    'ru': 'ru',
    'zh': 'zh',
    'ko': 'ko',
    'nl': 'nl',
    'pl': 'pl',
    'sv': 'sv',
    'da': 'da',
    'fi': 'fi',
    'no': 'no',
    'cs': 'cs',
    'hu': 'hu',
    'ro': 'ro',
    'sk': 'sk',
    'sl': 'sl',
    'bg': 'bg',
    'et': 'et',
    'lv': 'lv',
    'lt': 'lt',
    'uk': 'uk',
    'ar': 'ar',
    'tr': 'tr'
}

# 言語判別関数（エラーハンドリング追加）
def detect_language(text):
    try:
        lang = detect(text)
        # DeepLがサポートする言語にマッピング
        return DEEPL_SUPPORTED_LANGS.get(lang, "en")
    except LangDetectException:
        # 言語判別に失敗した場合はデフォルトで英語として扱う
        return "en"

# Google Translate フォールバック関数
async def translate_with_google(text, source_lang, target_lang):
    """Google Translateを使用した翻訳関数"""
    try:
        # Google Translateの言語コード変換（中国語繁体字 ↔ 韓国語）
        if target_lang == "KO":
            google_target = "ko"
        elif target_lang == "ZH-HANT":
            google_target = "zh-tw"  # Google Translateでは繁体字はzh-tw
        else:
            google_target = "ko"

        result = google_translator.translate(text, dest=google_target, src=source_lang)
        
        return {
            "success": True,
            "translated_text": result.text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "service": "Google Translate"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Google Translate エラー: {str(e)}",
            "service": "Google Translate"
        }

# 翻訳関数（DeepL + フォールバック対応）
async def translate_text(text, source_lang=None):
    """DeepLとGoogle Translateフォールバック対応翻訳関数"""
    try:
        # 言語を自動判定
        if not source_lang:
            detected_lang = detect_language(text)
        else:
            detected_lang = source_lang

        # 翻訳先言語を決定（中国語繁体字 ↔ 韓国語）
        if detected_lang == "zh" or detected_lang == "zh-tw" or detected_lang == "zh-hant":
            target_lang = "KO"  # 中国語 → 韓国語
        elif detected_lang == "ko":
            target_lang = "ZH-HANT"  # 韓国語 → 中国語繁体字
        else:
            # その他の言語は韓国語に翻訳
            target_lang = "KO"

        # まずDeepL APIを試す
        try:
            # DeepL APIパラメータ（短いテキストの場合は自動検出を使用）
            params = {
                "auth_key": DEEPL_TOKEN,
                "text": text,
                "target_lang": target_lang
            }
            
            # テキストが十分長い場合のみsource_langを指定
            if len(text.strip()) > 3:
                params["source_lang"] = detected_lang.upper()

            # API呼び出し
            response = requests.post(DEEPL_API_URL, data=params, timeout=10)

            if response.status_code == 200:
                response_json = response.json()
                translated_text = response_json["translations"][0]["text"]
                return {
                    "success": True,
                    "translated_text": translated_text,
                    "source_lang": detected_lang,
                    "target_lang": target_lang,
                    "service": "DeepL"
                }
            else:
                # DeepLでエラー発生時（無料枠切れなど）はフォールバックを使用
                print(f"🔄 DeepL API エラー（{response.status_code}）- Google Translateにフォールバック")
                return await translate_with_google(text, detected_lang, target_lang)

        except requests.exceptions.Timeout:
            print("🔄 DeepL API タイムアウト - Google Translateにフォールバック")
            return await translate_with_google(text, detected_lang, target_lang)
        except requests.exceptions.RequestException as e:
            print(f"🔄 DeepL API ネットワークエラー - Google Translateにフォールバック: {str(e)}")
            return await translate_with_google(text, detected_lang, target_lang)

    except Exception as e:
        # 予期しないエラーの場合もフォールバック
        print(f"🔄 予期しないエラー - Google Translateにフォールバック: {str(e)}")
        return await translate_with_google(text, "auto", "JA")

# 日本語翻訳専用関数（ボタン用）
async def translate_to_japanese(text, source_lang=None):
    """元のテキストを日本語に翻訳する関数"""
    try:
        # 言語を自動判定
        if not source_lang:
            detected_lang = detect_language(text)
        else:
            detected_lang = source_lang

        # DeepL APIで日本語に翻訳
        try:
            params = {
                "auth_key": DEEPL_TOKEN,
                "text": text,
                "target_lang": "JA"  # 日本語
            }

            if len(text.strip()) > 3:
                params["source_lang"] = detected_lang.upper()

            response = requests.post(DEEPL_API_URL, data=params, timeout=10)

            if response.status_code == 200:
                response_json = response.json()
                translated_text = response_json["translations"][0]["text"]
                return {
                    "success": True,
                    "translated_text": translated_text,
                    "source_lang": detected_lang,
                    "target_lang": "JA",
                    "service": "DeepL"
                }
            else:
                # DeepLでエラー発生時はGoogle Translateにフォールバック
                print(f"🔄 DeepL API エラー（{response.status_code}）- Google Translateにフォールバック")
                result = google_translator.translate(text, dest="ja", src=detected_lang)
                return {
                    "success": True,
                    "translated_text": result.text,
                    "source_lang": detected_lang,
                    "target_lang": "JA",
                    "service": "Google Translate"
                }

        except requests.exceptions.Timeout:
            print("🔄 DeepL API タイムアウト - Google Translateにフォールバック")
            result = google_translator.translate(text, dest="ja", src=detected_lang)
            return {
                "success": True,
                "translated_text": result.text,
                "source_lang": detected_lang,
                "target_lang": "JA",
                "service": "Google Translate"
            }
        except requests.exceptions.RequestException as e:
            print(f"🔄 DeepL API ネットワークエラー - Google Translateにフォールバック: {str(e)}")
            result = google_translator.translate(text, dest="ja", src=detected_lang)
            return {
                "success": True,
                "translated_text": result.text,
                "source_lang": detected_lang,
                "target_lang": "JA",
                "service": "Google Translate"
            }

    except Exception as e:
        print(f"❌ 日本語翻訳エラー: {str(e)}")
        return {
            "success": False,
            "error": f"翻訳エラー: {str(e)}"
        }

# 英語翻訳専用関数（ボタン用）
async def translate_to_english(text, source_lang=None):
    """元のテキストを英語に翻訳する関数"""
    try:
        # 言語を自動判定
        if not source_lang:
            detected_lang = detect_language(text)
        else:
            detected_lang = source_lang

        # DeepL APIで英語に翻訳
        try:
            params = {
                "auth_key": DEEPL_TOKEN,
                "text": text,
                "target_lang": "EN"  # 英語
            }

            if len(text.strip()) > 3:
                params["source_lang"] = detected_lang.upper()

            response = requests.post(DEEPL_API_URL, data=params, timeout=10)

            if response.status_code == 200:
                response_json = response.json()
                translated_text = response_json["translations"][0]["text"]
                return {
                    "success": True,
                    "translated_text": translated_text,
                    "source_lang": detected_lang,
                    "target_lang": "EN",
                    "service": "DeepL"
                }
            else:
                # DeepLでエラー発生時はGoogle Translateにフォールバック
                print(f"🔄 DeepL API エラー（{response.status_code}）- Google Translateにフォールバック")
                result = google_translator.translate(text, dest="en", src=detected_lang)
                return {
                    "success": True,
                    "translated_text": result.text,
                    "source_lang": detected_lang,
                    "target_lang": "EN",
                    "service": "Google Translate"
                }

        except requests.exceptions.Timeout:
            print("🔄 DeepL API タイムアウト - Google Translateにフォールバック")
            result = google_translator.translate(text, dest="en", src=detected_lang)
            return {
                "success": True,
                "translated_text": result.text,
                "source_lang": detected_lang,
                "target_lang": "EN",
                "service": "Google Translate"
            }
        except requests.exceptions.RequestException as e:
            print(f"🔄 DeepL API ネットワークエラー - Google Translateにフォールバック: {str(e)}")
            result = google_translator.translate(text, dest="en", src=detected_lang)
            return {
                "success": True,
                "translated_text": result.text,
                "source_lang": detected_lang,
                "target_lang": "EN",
                "service": "Google Translate"
            }

    except Exception as e:
        print(f"❌ 英語翻訳エラー: {str(e)}")
        return {
            "success": False,
            "error": f"翻訳エラー: {str(e)}"
        }

# Viewクラス（ボタンを含む）
class TranslationView(View):
    def __init__(self, original_text, source_lang):
        super().__init__(timeout=None)  # タイムアウトなし（永続化）
        self.original_text = original_text
        self.source_lang = source_lang

    @discord.ui.button(label="日本語", style=discord.ButtonStyle.primary, custom_id="translate_to_japanese")
    async def japanese_button(self, interaction: discord.Interaction, button: Button):
        """日本語翻訳ボタンがクリックされた時の処理"""
        # ボタンを無効化
        button.disabled = True
        await interaction.response.defer()

        # 元のテキストを日本語に翻訳
        japanese_result = await translate_to_japanese(self.original_text, self.source_lang)

        if japanese_result["success"]:
            # 既存のEmbedを取得して日本語訳を追加
            original_embed = interaction.message.embeds[0]
            current_description = original_embed.description

            # 日本語訳を追加
            new_description = current_description + "\n🇯🇵： " + japanese_result["translated_text"]

            # Embedを更新
            updated_embed = discord.Embed(
                description=new_description,
                color=original_embed.color
            )

            # メッセージを編集（ボタン無効化とEmbed更新）
            await interaction.message.edit(embed=updated_embed, view=self)
        else:
            # エラー時の処理
            await interaction.followup.send("❌ 日本語翻訳に失敗しました", ephemeral=True)

    @discord.ui.button(label="English", style=discord.ButtonStyle.primary, custom_id="translate_to_english")
    async def english_button(self, interaction: discord.Interaction, button: Button):
        """英語翻訳ボタンがクリックされた時の処理"""
        # ボタンを無効化
        button.disabled = True
        await interaction.response.defer()

        # 元のテキストを英語に翻訳
        english_result = await translate_to_english(self.original_text, self.source_lang)

        if english_result["success"]:
            # 既存のEmbedを取得して英語訳を追加
            original_embed = interaction.message.embeds[0]
            current_description = original_embed.description

            # 英語訳を追加
            new_description = current_description + "\n🇺🇸： " + english_result["translated_text"]

            # Embedを更新
            updated_embed = discord.Embed(
                description=new_description,
                color=original_embed.color
            )

            # メッセージを編集（ボタン無効化とEmbed更新）
            await interaction.message.edit(embed=updated_embed, view=self)
        else:
            # エラー時の処理
            await interaction.followup.send("❌ 英語翻訳に失敗しました", ephemeral=True)

# 起動時動作
@client.event
async def on_ready():
    print(f"✅ {client.user} として起動しました")
    print(f"📊 サーバー数: {len(client.guilds)}")
    print(f"🌍 全チャンネルで自動翻訳が有効です（中国語繁体字 ↔ 韓国語）")
    print(f"🔄 フォールバック: DeepL → Google Translate")
    print(f"🇯🇵🇺🇸 日本語・英語翻訳ボタン機能が有効です")

    # ボタンの永続化（Bot再起動後も動作）
    # ダミーのViewを追加して、既存のボタンをリッスン
    client.add_view(TranslationView(original_text="", source_lang="ja"))

    # 定期ヘルスチェックを開始
    asyncio.create_task(periodic_health_check())

# メッセージ処理
@client.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == client.user:
        return

    # 除外チャンネルチェック
    if message.channel.id in excluded_channels:
        return

    # 指定チャンネル限定モードの場合
    if DISCORD_CHANNEL_ID and message.channel.id != DISCORD_CHANNEL_ID:
        return

    # 空のメッセージや短すぎるメッセージは無視
    if not message.content or len(message.content.strip()) < 2:
        return

    # Bot終了コマンド（管理者のみ）
    if message.content.startswith("おやすみttt"):
        # 管理者権限チェック（オプション）
        if message.author.guild_permissions.administrator:
            await message.channel.send("おやすみ！また明日！ 🌙")
            await client.close()
        else:
            await message.channel.send("❌ 管理者のみがこのコマンドを使用できます")
        return

    # ヘルプコマンド
    if message.content.startswith("!help") or message.content.startswith("!ヘルプ"):
        help_embed = discord.Embed(
            title="🤖 翻訳Bot ヘルプ",
            description="自動翻訳機能について",
            color=0x00ff00
        )
        help_embed.add_field(
            name="📝 機能",
            value="• 中国語繁体字→韓国語\n• 韓国語→中国語繁体字\n• 日本語・英語翻訳ボタン",
            inline=False
        )
        help_embed.add_field(
            name="🔧 コマンド",
            value="• `!help` - このヘルプを表示\n• `おやすみttt` - Bot停止（管理者のみ）",
            inline=False
        )
        if excluded_channels:
            help_embed.add_field(
                name="🚫 除外チャンネル",
                value=f"以下のチャンネルでは翻訳無効:\n{', '.join(str(ch_id) for ch_id in excluded_channels)}",
                inline=False
            )
        await message.channel.send(embed=help_embed)
        return

    # 翻訳処理
    try:
        # 翻訳実行
        result = await translate_text(message.content)

        if result["success"]:
            # 翻訳先言語に応じて国旗絵文字を追加
            if result["target_lang"] == "KO":
                flag_prefix = "🇰🇷： "
            elif result["target_lang"] == "ZH-HANT":
                flag_prefix = "🇹🇼： "
            else:
                flag_prefix = ""
            
            # 翻訳サービスに応じて色を変更
            color = 0x00ff00 if result.get("service") == "DeepL" else 0x4285f4  # DeepL=緑, Google=青

            # 埋め込み形式で翻訳後のテキストのみを表示
            embed = discord.Embed(
                description=flag_prefix + result["translated_text"],
                color=color
            )

            # 韓国語翻訳ボタンを含むViewを作成
            view = TranslationView(
                original_text=message.content,
                source_lang=result["source_lang"]
            )

            await message.channel.send(embed=embed, view=view)
        else:
            # エラー時の表示
            error_embed = discord.Embed(
                title="❌ 翻訳エラー",
                description=result["error"],
                color=0xff0000
            )
            if "details" in result:
                error_embed.add_field(
                    name="詳細",
                    value=result["details"][:1000],  # 長すぎる場合は切り詰め
                    inline=False
                )
            await message.channel.send(embed=error_embed)

    except Exception as e:
        # 予期しないエラー
        await message.channel.send(f"❌ 予期しないエラーが発生しました: {str(e)}")
        print(f"Error in on_message: {e}")

# エラーハンドリング
@client.event
async def on_error(event, *args, **kwargs):
    print(f"エラーが発生しました: {event}")
    import traceback
    traceback.print_exc()

# Bot実行
if __name__ == "__main__":
    try:
        # Keep-alive機能を起動
        keep_alive()
        
        # Discord botを起動
        client.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Discord トークンが無効です")
    except Exception as e:
        print(f"❌ Bot起動エラー: {e}")