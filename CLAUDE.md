# kindle-cap

Kindle for Mac の書籍を撮影 → PDF → OCR → markdown / EPUB にする個人用 CLI。使い方と設計は `README.md`、変更履歴は `CHANGELOG.md`。

## 音声での声掛け・進捗報告 (voicevox)

このプロジェクトの開発中は、`.mcp.json` の voicevox MCP（`@kajidog/mcp-tts-voicevox`、VOICEVOX Engine は `http://127.0.0.1:50021`）で **四国めたん（ノーマル、speaker 2）・1.5 倍速** を使い、ユーザーに音声で声掛け・進捗報告すること。

- 話すタイミング: 作業の開始時、長い処理（テスト・CI 待ち・実機検証・OCR）の前後、PR/merge/release の完了時、ユーザーの判断が必要になった時
- 1 回の発話は 1〜2 文。文字での報告の代わりではなく補助。詳細は従来どおりテキストで出す
- ツールは `voicevox_speak`。`speaker` と `speedScale` は `.mcp.json` の既定（2 / 1.5）に任せ、個別指定しない
- MCP ツールが見当たらない（セッション開始時に承認されていない等）場合は、Engine の REST API を直接叩いて代替する:

  ```bash
  text="進捗報告です"
  curl -s -X POST "http://127.0.0.1:50021/audio_query?speaker=2" --get --data-urlencode "text=$text" > /tmp/q.json
  python3 -c "import json;d=json.load(open('/tmp/q.json'));d['speedScale']=1.5;json.dump(d,open('/tmp/q.json','w'))"
  curl -s -X POST "http://127.0.0.1:50021/synthesis?speaker=2" -H 'Content-Type: application/json' -d @/tmp/q.json -o /tmp/v.wav && afplay /tmp/v.wav
  ```

- Engine が起動していなければ（`curl http://127.0.0.1:50021/version` が失敗）、VOICEVOX.app を起動するようユーザーに一言伝え、音声なしで続行する
