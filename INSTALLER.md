# WCP 词书一键安装器（Install-WCP-Wordbooks.ps1）

> 本文件迁自 `hanserdesu/WCP-Wordbook-Hub` 的 README；安装器与资源契约以本文件为准。

`Install-WCP-Wordbooks.ps1` is the resource delivery boundary. A language pack
is discovered from a GitHub repository and released as assets; the installer
does not need a new language-specific code path when the pack follows this
contract.

## Repository and release contract

Use a repository named `japanese` or `WCP-*-Wordbook` under the configured
GitHub owner. The catalog-pinned resource release and the latest GitHub
release are both inspected. The candidate with the richest verified asset set
wins, so a small core/mod release does not hide a newer resource-only release.
Each release is inspected for either:

- `wcp-wordbook.json`, `wordbook-manifest.json`, or `release-manifest.json`;
- or archive assets whose names contain `word`/`audio` and
  `sentence`/`example`.

The preferred manifest contains an `assets` array. Every asset has `kind`,
`name`, `size`, `sha256`, and `url` (the installer can fill `url` from the
release asset with the same name). `kind` may be `payload`, `pack`,
`word_audio`, `sentence_audio`, or `slot_manifest`. A pack may also publish
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
