# WCP 词书一键安装器（Install-WCP-Wordbooks.ps1）

本文件迁自早期的 `WCP-Wordbook-Hub` 分发仓 README；该分发仓已于 2026-09-21 收拢并入本仓库，安装器与资源契约以本文件为准。

`Install-WCP-Wordbooks.ps1` is the resource delivery boundary. A language pack
is discovered from a GitHub repository and released as assets; the installer
does not need a new language-specific code path when the pack follows this
contract.

## Repository and release contract

Use `hanserdesu/WCP-MultiLanguage` (one resource tag per language,
`wcp-<lang>-resources-*`) plus `hanserdesu/japanese` (legacy `wcp-jp-*` tags
map to the catalog id `ja`) under the configured GitHub owner. Discovery
groups a repository's releases by the language segment of the release tag, so
one repository may carry many wordbooks and never mixes another language's
assets into a row; the richest verified asset set wins.
Each release is inspected for either:

- `wcp-wordbook.json`, `wordbook-manifest.json`, or `release-manifest.json`;
- or archive assets whose names contain `word`/`audio` and
  `sentence`/`example`.

The preferred manifest contains an `assets` array. Every asset has `kind`,
`name`, `size`, `sha256`, and `url` (the installer can fill `url` from the
release asset with the same name). `kind` may be `payload`, `pack`,
`word_audio`, `sentence_audio`, `slot_manifest`, or `mod`.

## Mod payload (catalog top-level `mods` block)

The BepInEx plugins (WcpHost, CustomSlotsMod, BookNameMod) are global: they do
not belong to any single wordbook row. The catalog therefore carries a
top-level `mods` object (`version`, `repo`, `assets`), backed by the
`wcp-mods-v*` release on `hanserdesu/WCP-MultiLanguage`. Its payload zip uses
BepInEx-relative entry paths (`plugins/*.dll`, mirroring the Japanese one-click
installer payload), and the installer expands it into `<game>\BepInEx` before
installing any wordbook. `hub-state.json` records it under a top-level `mods`
key (`version` + per-asset sha256), so `-Update` re-fetches only when the
release changes. The zip is verified by sha256 before extraction and entries
are expanded individually with traversal rejection (a `..` entry aborts). A pack may also publish
`status: "pending_release"` while its code/data is being prepared; it appears
in `-List` but cannot be selected for installation until it is `available`.

The catalog entry also declares `id`, `language`, `display_name`, `repo`,
`version`, `word_count`, `es3_prefix`, and `disk.extract_mb`. The last value is
the estimated expanded size used for the preflight peak-space check.
When a release declares no `disk.extract_mb` (a minimal manifest), the installer
prints `解压 未知` in the list and appends an explicit warning to the
compatibility line instead of treating 0 MB as a measurement. Publishing a
`wcp-wordbook.json` asset with `disk.extract_mb`, `word_count`, and
`es3_prefix` is the supported way to make that number exact.

Adding a language therefore means: create the repository, publish a release
with the resource assets, and optionally add the catalog entry for nicer
metadata. Neither the host nor these tests enumerate languages, so no code
change is required - re-run the installer and the new book appears in the list.

For the unified host, set `strategy.assembly` to `$host` and
`strategy.type` to `WcpHost.GenericLanguageStrategy` when the pack follows the
standard resource schema. The host binds the manifest language at load time;
the pack does not need a language DLL or a new host test path. A language that
needs genuinely different display behavior may still ship a private strategy
assembly inside its own pack.

## Installer self-update

`run-installer.ps1` injects `WCP_INSTALLER_VERSION`; `Install-WCP-Wordbooks.ps1`
compares it against `release-index.json` and only offers to switch when a
different version is published. The check never blocks an install: every
failure path prints one line and continues with the current version, and
`-Offline` / `-Plan` / `-List` skip it entirely.

The index is read from three sources in order, the first one that parses into
an `installer_version` wins:

1. `https://raw.githubusercontent.com/hanserdesu/WCP-MultiLanguage/main/release-index.json`
   - the repository-root copy, written by `tools/release/build_installer.py`
   and committed on every release. It costs no GitHub API quota and is not
   affected by release-asset CDN caching.
2. the `release-index.json` asset of the newest `wcp-mods-*` release, fetched
   through its API asset URL with `Accept: application/octet-stream`.
   Without that header GitHub answers with asset metadata JSON, the parse
   yields no `installer_version`, and the update prompt silently never fires
   (this was the shipped behaviour up to v0.1.3).
3. the same asset through its `browser_download_url`, which goes through the
   CDN and therefore keeps working when `api.github.com` is rate limited.

The downloaded core installer is verified by sha256 before anything is
switched, and the new package is expanded into a fresh directory first.

## Twenty logical custom slots

The optional `slot_manifest` asset is a UTF-8 JSON document consumed by
`Japanese/mod_custom_slots`. Its root is `SlotState`:

```json
{
  "schema": 1,
  "selected": 0,
  "slots": [
    {
      "number": 1,
      "id": "fr-core",
      "name": "Français Core",
      "language": "fr",
      "owner": "mod",
      "managed": true,
      "nativeSlot": 0,
      "words": ["bonjour", "merci", "...", "...", "..."]
    }
  ]
}
```

The host normalizes the list to 20 rows. Existing native books are imported as
`external`; selecting an external row never overwrites a non-mod native book.
Only rows marked `managed: true` are eligible for the mod's language-resource
service. The four native game fields remain an implementation boundary, so no
language pack is coupled to a fictitious `SelfBookList5` field.

## Commands

### 双击使用（给玩家）

- `一键安装词书.cmd` 列出全部词书，输入编号（可逗号分隔或 `all`）即可选择安装。
- `更新词书资源.cmd` 等价于 `-Update`：默认选中已安装的词书，回车就会更新。

Both launchers are shipped verbatim from the repository root: the packaging
script copies them instead of generating its own two-line replacement. Each one
re-launches itself via `cmd.exe /d /k call "%~f0" --keep-open`, so the console
survives the end of the run and the player can still read the status. The
launcher exports `WCP_KEEP_OPEN=1`, and `run-installer.ps1` only promises a
persistent window when that variable is actually set.

安装前会按 `hub-state.json` 里记录的 SHA-256 逐项比对，只有内容变过的资源
才重新下载，所以“重新运行安装器”本身就是更新。两个 `.cmd` 只负责找到
PowerShell 并让窗口保持打开，全部中文提示都在带 BOM 的 `.ps1` 里，避免代码页
乱码；批处理内容刻意保持纯 ASCII。

```powershell
.\Install-WCP-Wordbooks.ps1 -List
.\Install-WCP-Wordbooks.ps1 -Plan -Books fr,ja -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Books fr,ja -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Update -GameDir 'D:\Games\WCP'
```

`-Plan` reports changed download bytes, extraction bytes, peak bytes, final
bytes, reserve, free space, and the compatibility result. `-Update` downloads
only assets whose SHA-256 differs from the installed state. `-Offline` uses the
checked-in catalog and the local cache without contacting GitHub.

## 资源包发布流程

每种语言的语音资源来自游戏缓存目录
`%USERPROFILE%\AppData\LocalLow\WCP\wcp\<lang>_{word,sentence}_audio`，
打成与日语包同规格的 zip（平铺 mp3、`ZIP_STORED`、无目录项），文件名固定为
`wcp-<english>-audio-{words,sentences}.zip`。发布走四步：

```powershell
# 1) 打包（跳过已有 zip，逐语言把 sha256/size 写进 build-summary.json）
python _local\release\build_all_languages.py --only de,es
# 2) 生成每语言的 release-manifest.json / notes.md 与精确解压占用
python _local\release\make_release_manifests.py
# 3) 建 draft release -> 上传 -> 用 GitHub 回的 digest 核对本地 sha256 -> 才发布
python _local\release\publish_release.py de,es
#    （上传中断留下半包时加 --repair：删掉对不上的资产再传一次）
# 4) 把通过校验的 url/size/sha256 写回 catalog.json
python tools\apply_resource_releases.py <发布的 releases.json> --keep-repo ja
```

`publish_release.py` 在资源没有全部通过 size + sha256 核对前不会把 draft 转正，所以
失败只会留下一份 draft，玩家拿不到未校验的字节。

上传是 GB 级流量，本机固定走良心云线路：Clash Verge 全局 `Script.js` 把 `github.com` /
`githubusercontent.com` 指向 `🎈 GitHub线路`（良心云），用户级 `HTTPS_PROXY` 指向
`http://127.0.0.1:7897`；XSUS 订阅只保留 AI 服务，不承担资源上传。上传时可用
`_local\proxy\pipe_client.py chains github` 确认实际链路。

日语是例外：日语语音包留在 `hanserdesu/japanese`，`catalog.json` 的 `ja` 条目固定指向该仓库的
公开稳定 tag（历史 draft 版本不在目录中引用）。
