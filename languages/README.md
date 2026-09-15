# languages/ — 各语言工程集成目录

本目录是 9 个语言工程在 WCP-MultiLanguage 仓库里的落点。每个子目录都是原语言仓库
「工作区状态」的完整快照（tracked 文件 + 集成时尚未提交的改动），内部相对路径保持原样，
因此各工程自己的 `tools/*.py`、`verify_all_*.py` 仍可在该目录内直接运行。

| 目录 | 语言 / 词书 id | 来源仓库 | 集成时 HEAD | 状态 |
|---|---|---|---|---|
| `ja/` | 日语 / `ja` | `hanserdesu/japanese` | `5283a39` | 稳定版 `wcp-jp-v1.2.2` 已发布供群友使用；在研改动随工作区一并集成到本目录 |
| `fr/` | 法语 / `fr` | `hanserdesu/WCP-French-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-fr-resources-v1.0.0` |
| `ru/` | 俄语 / `ru` | `hanserdesu/WCP-Russian-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-ru-resources-v1.0.0` |
| `de/` | 德语 / `de` | `hanserdesu/WCP-German-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-de-resources-v1.0.0` |
| `es/` | 西班牙语 / `es` | `hanserdesu/WCP-Spanish-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-es-resources-v1.0.0` |
| `pt/` | 葡萄牙语 / `pt` | `hanserdesu/WCP-Portuguese-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-pt-resources-v1.0.0` |
| `ko/` | 韩语 / `ko` | `hanserdesu/WCP-Korean-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-ko-resources-v1.0.0` |
| `ar/` | 阿拉伯语 / `ar` | `hanserdesu/WCP-Arabic-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-ar-resources-v1.0.0` |
| `yue/` | 粤语 / `yue` | `hanserdesu/WCP-Cantonese-Wordbook` | 见 PROVENANCE | 资源由本仓库发布 `wcp-yue-resources-v1.0.0` |

逐语言的来源 SHA、文件数、内容摘要（sha256）与排除项记录在 [PROVENANCE.json](PROVENANCE.json)。

## 提交规则

**以后所有语言的项目改动都在本仓库提交**：语言工程改 `languages/<code>/`，宿主、槽位、
书名层、资源包契约与安装器改仓库根部对应目录。原语言仓库作为历史归档保留，不再作为开发入口；
日语词书本体与日语语音包的 Release 仍留在 `hanserdesu/japanese`，其余语言的语音包由本仓库发布。

## 集成范围

- **全部集成**：来源仓库 tracked 的每个文件都在，工作区里未提交的修改与新增文件同样集成，
  不做任何删减——本目录同时是「回滚前那批在研改动」的保存处。
- **只排除可再生的大体积产物**：`output/release/`、`output/installer_pkg/`、`output/*/backup/`、
  `gitee-parts/`、`*.zip`、虚拟环境、`__pycache__`、工具缓存，以及各语言根目录下与仓库根部
  `packs/` 重复的打包产物。这些要么由 Releases 承载，要么由各工程 `tools/` 现场重建。
- 具体到每个语言排除了哪些、多少字节，看 [PROVENANCE.json](PROVENANCE.json) 的 `excluded` 字段。

## 复现与校验

```powershell
# 重新集成（默认 dry-run，只打印计划；--apply 才写文件）
python tools\integrate_languages.py --apply

# 逐文件 sha256 校验 languages/<code>/ 与原仓库工作区是否一致
python tools\verify_integration.py
```

## 日语回滚说明

`hanserdesu/japanese` 的 `master` 已回滚到 `8e48f6a`（tag `wcp-jp-v1.2.2`），即群友正在使用的
稳定版；回滚前的 12 个提交完整保存在本地分支 `archive/pre-freeze-2026-09-15` 与 reflog 中，
其工作区内容已随本目录 `ja/` 一并入库。`ja/` 目录里也包含工作区中主动删除的
`packs/{de,fr,ru}/manifest.json`——这些语言的资源包清单以仓库根部 `packs/` 为准。
