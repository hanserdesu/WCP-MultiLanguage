# 韩语词库项目 —— 生产规则（用户指定，持久生效）

1. **主会话直写**：词表精选、中文释义、例句等所有内容生产由主会话直接、持续、增量地写入文件（随写随落盘）。**禁止**把大段内容生产分块派发给子代理批量跑 —— 子代理容易丢输出。
2. 后台进程（Python 脚本、edge-tts 音频作业等）不受此限，可以后台运行。
3. 每写完一批立即用校验脚本收口，保证任何时刻磁盘上都是干净可续的状态；下一轮可直接续跑。
4. 此规则已同步写入全局 `C:\Users\hanserdesu\.zcode\AGENTS.md`（Working agreements），适用于 D:\ATooManyLanguage\German、D:\ATooManyLanguage\French、D:\ATooManyLanguage\Russian、D:\ATooManyLanguage\Japanese 及 D:\korean 项目。
