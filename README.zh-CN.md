# BlockStart Launcher

> 一款面向 Windows 平台的 Minecraft（MC）Java 版第三方启动器。

BlockStart Launcher（简称 BSL）是 Windows 上的 Minecraft Java 版启动器，当前版本 V0.5.3b。它把游戏版本下载、多版本实例管理、正版与离线账户登录、Fabric / Forge / NeoForge / Quilt 加载器安装、Modrinth 模组与整合包、资源包与光影、文件校验与崩溃诊断集中在同一个界面里，适合需要在本机维护多个独立游戏环境的玩家。

[English](README.md) · [更新记录](CHANGELOG.md) · [快速上手（零基础）](docs/QUICKSTART.zh-CN.md)

## 快速开始

1. 从 [Releases](https://github.com/Family-GH/BlockStartLauncher/releases/latest) 下载 `BlockStartLauncherPortable.zip`，解压到纯英文路径（如 `D:\Games\BSL`）。
2. 双击 `BlockStartLauncherPortable.exe`。SmartScreen 提示时选「更多信息 → 仍要运行」。
3. 账户页登录 Microsoft 账户，或先建一个离线账户。
4. 主页点「新建实例」，选游戏版本（需要模组就顺带选加载器），再点「启动游戏」。
5. 首次启动会自动下载游戏文件，之后每次只需点一次启动。

完整步骤、每一步对应的按钮，以及最容易出错的十几个操作，见 [快速上手文档](docs/QUICKSTART.zh-CN.md)。

## 功能特性

### 实例管理

- 支持创建多个相互隔离的游戏实例，每个实例拥有独立的 mods、存档、配置与资源包目录，互不影响。
- 新建实例时选择游戏版本即可，实例名称可自定义；支持删除实例、单独下载版本、重试版本列表。
- 每个实例可单独配置模组加载器、Java 路径、最大内存、窗口尺寸、全屏、额外启动参数与自动进入的服务器地址；未单独配置时跟随全局默认值。
- 支持 Fabric、Forge、NeoForge、Quilt 四种加载器，启动时自动安装，无需手动下载安装程序。

### 账户与皮肤

- 支持微软正版账户登录（设备码流程）与离线账户；登录后的凭证保存在本地，下次启动直接使用。
- 正版账户可在皮肤与披风页面查看正反面预览，上传 64×64 或 64×32 格式的 PNG 皮肤，选择经典 Steve 或纤细 Alex 模型（支持自动识别，也可手动切换），恢复默认皮肤，以及启用或隐藏已拥有的披风；预览中的第二层（帽子、外套等）可开关。
- 64×32 旧皮肤缺失的左臂、左腿会自动镜像补齐。

### 游戏下载与 Java 环境

- 下载线路提供自动选择（镜像优先）、BMCLAPI 镜像与官方源三种模式，下载失败时自动切换备选地址。
- 启动前自动检索本机 Java 环境（注册表、常见安装目录及其他启动器的运行库目录）；未检测到时可手动指定 `java.exe`，也可由启动器下载适配的 Java 运行环境。
- 启动时自动补齐缺失的版本文件、资源文件与运行库，下载过程可查看进度并随时中止。

### 模组管理

- 内置 Modrinth 模组搜索，在启动器内即可查看模组介绍、分类、支持的游戏版本与加载器，选择对应版本下载到当前实例。
- 已安装模组支持启用 / 禁用（通过修改扩展名保留文件）、删除与打开模组文件夹。
- 自动扫描加载器混用与重复 modid 问题，并在界面中给出提示。

### 整合包导入

- 支持 `.mrpack`、CurseForge 压缩包、MultiMC 以及标准 `.minecraft` 目录结构的整合包，可拖拽或选择文件导入。
- 导入时自动识别游戏版本与加载器，创建实例并从 Modrinth 补齐缺失模组，缺失内容会在界面中列出，导入过程可中止。

### 资源包与光影

- 支持在启动器内搜索 Modrinth 上的资源包与光影包，直接下载到当前实例对应目录。

### 修复与诊断

- 文件校验按版本清单核对 jar、assets 与 libraries，列出缺失或校验不符的文件，支持修复选中文件或全部修复，并提供仅重建运行库的进阶选项。
- 可对启动器自身进行自检并执行修复。
- 游戏崩溃后可读取最新崩溃报告与日志末尾，按常见报错类型（Java 版本不匹配、模组冲突、内存不足等）给出判断。

### 主页与状态总览

- 主页展示启动流程、Java 与内存、磁盘检查结果，以及自动进服服务器的在线人数与延迟（Server List Ping 协议）。
- 提供打开实例目录、备份存档、进入修复工具的快捷入口；检测到新版本时在此提示，可忽略指定版本。

### 界面与个性化

- 提供深、浅两套主题，页面动画可关闭，低配设备可获得更流畅的体验。
- 支持自定义背景图片与本地背景音乐目录（通过 Windows MCI 播放）。
- 全局可设置游戏内存、JVM 高级参数、窗口大小、全屏与自动进服地址；游戏目录可更换至其他磁盘，并保留最近使用过的位置记录。

### 启动器更新

- 默认检查 GitHub Releases 更新；也可在设置中填写多个 JSON 清单地址，启动器合并所有来源后选取版本号最高的一项，单个地址下载失败时自动切换。

## 下载与运行

最新构建在 [Releases 页面](https://github.com/Family-GH/BlockStartLauncher/releases/latest) 下载。

| 版本 | 文件 | 运行方式 |
| --- | --- | --- |
| 便携版 | `BlockStartLauncherPortable.zip` | 推荐。解压到任意目录，运行其中的 `BlockStartLauncherPortable.exe`；启动时不解压，不会触发单文件类的安全软件提示。 |
| 单文件版 | `BlockStartLauncher.exe` | 直接运行，首次启动会解压到 `%LOCALAPPDATA%\BlockStartLauncher`。 |

同样的构建也保存在 `BlockStartLauncher/dist` 中，按 GitHub 单文件 25MB 的限制拆成若干分片，并附带记录每个分片 SHA-256 的清单；`start_blockstart.bat` 会在首次运行时合并单文件版分片并启动。

启动器需要管理员权限写入游戏目录，权限不足时会弹出 UAC 提示。

手动校验或还原分片（Python 3.9+，仅使用标准库）：

```bat
python tools\release_chunks.py verify BlockStartLauncher\dist\BlockStartLauncher.exe.manifest.json
python tools\release_chunks.py restore BlockStartLauncher\dist\BlockStartLauncher.exe.manifest.json --dest BlockStartLauncher\dist\BlockStartLauncher.exe
```

## 数据存储与安全

- 数据默认存放于 `%LOCALAPPDATA%\BlockStartLauncher`，包含游戏文件、实例、存档、账户与设置；迁移电脑时可整体复制，账户需重新登录。
- 账户令牌使用 Windows DPAPI 按当前 Windows 用户加密保存；配置文件与账户文件写入前保留 `.bak` 备份，主文件损坏时尝试回滚。
- 存档备份先写入临时文件，完成后再改名；取消或失败时自动清理，不会留下损坏的压缩包。

## 从源码构建

```bat
py -3 -m pip install -r BlockStartLauncher\requirements.txt
py -3 BlockStartLauncher\build_exe.py
```

单文件构建输出 `dist/BlockStartLauncher.exe`；构建前设置 `BSL_ONEDIR=1` 则产出口袋版。构建完成后用 `tools/release_chunks.py` 重新分片，分片数量变化时需同步修改启动脚本中的分片列表。

## 已知限制

- 程序未购买商业代码签名证书，新设备首次运行时 Windows 可能弹出 SmartScreen 提示，选择“更多信息 → 仍要运行”即可。
- 单文件版每次启动都要解压到 `.bsl_runtime`，部分安全软件会拦截；便携版可以避开这一提示，但未签名程序仍可能被一般性拦截。
- 微软登录流程仅在错误分支与离屏环境下完成验证，未使用真实账户跑完整授权流程。
- 目前仅支持 Windows 系统。
- 启动器本身不提供 Minecraft 游戏本体，联机与官方皮肤功能仍需合法拥有的 Microsoft 账户。

## 常见问题

**双击后提示“Windows 已保护你的电脑”？**
程序没有商业代码签名证书。点「更多信息 → 仍要运行」。需要彻底消除提示只能购买签名证书，改名或压缩都无效。

**杀毒软件报拦截、提示修改关键 DLL？**
单文件版每次启动都会解包到 `.bsl_runtime`，容易被拦截。改用便携版，或选择「允许本次操作」。

**游戏启动失败，提示 Java 相关错误？**
设置页 →「Java 运行环境」重新检测，或手动选择 `bin\java.exe`；也可以让启动器下载对应运行时。

**版本列表一直是空的？**
检查网络后点「重试版本列表」，或到「设置」→「下载」切换下载线路。

**模组装了却不生效？**
确认模组的游戏版本与加载器跟当前实例一致，并且该模组已勾选启用；混用加载器会被启动前提示。

**换电脑后账户没了？**
账户凭证按 Windows 用户加密，不能跨机器解密，重新登录即可；存档和实例可以直接拷数据目录。

**启动器需要联网吗？**
首次下载游戏版本、搜索模组、检查更新时都需要；已经装好的版本可以离线启动。

## 目录结构

```text
BlockStartLauncher/
  run.py                 程序入口、UAC 检查、QApplication 初始化
  config.py              版本号、路径与更新源配置
  build_exe.py           PyInstaller 构建脚本
  version_info.txt       Windows 版本资源
  core/                  与界面无关的业务逻辑
  ui/                    界面页面与组件
  dist/                  发布分片与启动脚本
tools/
  release_chunks.py      分片拆分、校验与还原脚本
```
