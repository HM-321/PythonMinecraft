# LANマルチプレイ

## 配布物

- Mac: `MinecraftBuild.app`
- Windows: `MinecraftBuildServer.exe`

利用者側にPythonやライブラリのインストールは不要です。配布用ファイルは、それぞれMac上またはWindows上でビルドします。

## Windowsサーバーの起動

1. サーバー用フォルダーに `MinecraftBuildServer.exe` を置きます。
2. `MinecraftBuildServer.exe` をダブルクリックします。ワールドを指定しない場合は `saves\\server_world.json` が自動作成されます。
3. 既存ワールドを使う場合だけ、コマンドプロンプトで次を実行します。

```text
MinecraftBuildServer.exe --world saves\\新規ワールド.json
```

ポートを変更する場合は `--port 25565` のように指定します。既定ポートはTCP `25565` です。

Windows Defender Firewallの確認が表示されたら、プライベートネットワークで通信を許可します。表示されない場合は、Windowsのファイアウォール設定で `MinecraftBuildServer.exe` のTCP通信を許可してください。

## Macから参加

MacとWindows PCを同じWi-FiまたはLANに接続します。Windows PCのLAN IP（例: `192.168.1.20`）を確認し、Mac版アプリのマルチプレイ画面へ入力します。

ワールドの作成・保存はWindowsサーバー側で行います。サーバーを終了する前にコンソールへ `Ctrl+C` を入力してください。

## 一人プレイ

Windowsサーバーが起動していなくても、Mac版アプリの一人プレイから従来どおりローカルワールドを遊べます。
