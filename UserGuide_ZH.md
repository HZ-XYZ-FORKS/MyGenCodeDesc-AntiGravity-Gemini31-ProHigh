# 用户指南：aggregateGenCodeDesc

欢迎阅读 `aggregateGenCodeDesc` 工具的用户指南。该工具用于精准统计并聚合特定时间窗口内，代码库中所存活代码的 AI 生成占比。

## 快速入门 (Quick Start)
最快的使用方式是在本地的 Git 仓库中使用算法 A (动态 Blame溯源) 直接运行该工具：

```bash
# 1. 切换至目标仓库的根目录
cd /path/to/your/git/project

# 2. 运行计算工具
python aggregateGenCodeDesc.py \
  --repoURL $(git config --get remote.origin.url) \
  --repoBranch main \
  --startTime 2026-03-01T00:00:00Z \
  --endTime 2026-03-31T23:59:59Z \
  --genCodeDescDir /path/to/gen_code_data \
  --alg A \
  --threshold 60
```

## 概述
`aggregateGenCodeDesc` 将分析特定快照下的存活代码，并通过以下三个维度计算 AI 生成占比：
1. **加权占比 (Weighted Mode)**：以 `(genRatio / 100)` 的总和除以总存活代码行数。
2. **全比例 AI (Fully AI Mode)**：完全由 AI 生成的代码行占比 (`genRatio == 100`)。
3. **主导 AI (Mostly AI Mode)**：主要由 AI 生成的代码行占比 (`genRatio >= threshold` 阈值)。

---

## 完整使用说明

```bash
python aggregateGenCodeDesc.py \
  --repoURL <URL标识> \
  --repoBranch <分支名称> \
  --startTime <ISO8601起始时间> \
  --endTime <ISO8601结束时间> \
  --genCodeDescDir <目录路径> \
  [--alg <A|B|C>] \
  [--patchesDir <目录路径>] \
  [--threshold <0-100>] \
  [--log-level <DEBUG|INFO|WARN|ERROR>]
```

### 必需参数
- `--repoURL`: 目标代码库的标准 URL (例如：`https://github.com/EnigmaWU/project`)。**注意：** 因为该参数是一个身份校验标识 (Key)，它的值**必须**与提前生成的 `genCodeDesc` JSON 元数据内部的 `REPOSITORY.repoURL` 完全匹配！
- `--repoBranch`: 要分析的分支(Git)或路径(SVN)名称。
- `--startTime`: 统计时间窗口的起点 (ISO 8601 格式，例如 `2026-01-01T00:00:00Z`)。
- `--endTime`: 统计时间窗口的终点。
- `--genCodeDescDir`: 存储所有 commit 的 `genCodeDesc` JSON 元数据文件的本地目录路径。

### 可选参数
- `--alg`: 计算所用的算法 (`A`、`B` 或 `C`)。默认值为 `A`。
  - `A` (动态 Blame): 最高精度。必须在代码库的真实 checkout 文件夹内部运行，以确保代码库能被执行 `git/svn blame`。
  - `B` (离线差异重放): 离线计算。增量回放 diff 更改，配合 `--patchesDir` 参数使用。
  - `C` (内嵌 Blame): 纯离线环境，零 VCS 访问要求。直接处理 `v26.04` 协议格式数据。
- `--patchesDir`: **仅在使用 `--alg B` 时必需**。指定包含提前抓取好的 diff 补丁文件 (localCommitPatches) 的目录路径。
- `--threshold`: 定义“主导 AI”维度的阈值百分比 (0-100)。默认值为 `60`。
- `--log-level`: 运行时的诊断输出级别。可选项为 `DEBUG`、`INFO`、`WARN`、`ERROR`。默认值为 `INFO`。

---

## 分算法详细演示 (以组合场景为例)

### 1. 算法 A: 动态 Blame (适用 Git/SVN)
在使用 AlgA 时工具会直接查询代码库本身。因此，此命令**必须**在你存有项目代码的实际文件夹（克隆下来的根目录）内执行。
```bash
cd /path/to/your/git_or_svn_checkout
python aggregateGenCodeDesc.py \
  --repoURL https://github.com/EnigmaWU/MyProject \
  --repoBranch develop \
  --alg A \
  --startTime 2026-01-01T00:00:00Z \
  --endTime 2026-04-01T00:00:00Z \
  --genCodeDescDir ./my_metadata
```

### 2. 算法 B: 离线差异重放 (适用 Git/SVN)
AlgB 在离线环境中工作。因为它不执行实时的动态 blame，所以你可以从**任何地方**安全地执行它。只要为它提供了元数据目录和差异补丁目录即可。
```bash
python aggregateGenCodeDesc.py \
  --repoURL https://svn.example.com/repo \
  --repoBranch /trunk \
  --alg B \
  --startTime 2026-02-01T00:00:00Z \
  --endTime 2026-02-28T23:59:59Z \
  --genCodeDescDir /offline/svn_metadata \
  --patchesDir /offline/svn_localCommitPatches
```

### 3. 算法 C: 内嵌 Blame (当前仅支持 v26.04)
AlgC 完全基于其拥有自我推导能力的 `v26.04` 格式元数据文件。它**不需要**任何 VCS 的访问许可——无补丁需求、无需代码库。纯依靠累计和抵消来定位代码行。
```bash
python aggregateGenCodeDesc.py \
  --repoURL https://gitlab.internal/core/auth \
  --repoBranch main \
  --alg C \
  --startTime 2026-01-01T00:00:00Z \
  --endTime 2026-04-19T00:00:00Z \
  --genCodeDescDir /offline/v2604_metadata \
  --threshold 80
```

---

## 期望输出格式
工具将会在标准输出 (`stdout`) 打印一个符合 `genCodeDesc` v26.03 协议格式架构的 JSON 对象。你期望的三个维度的统计结果会被整洁地置于 `SUMMARY` 块内部。

```jsonc
{
  "protocolName": "generatedTextDesc",
  "protocolVersion": "26.03",
  "SUMMARY": {
    "totalLines": 5000,
    "weightedModeRatio": 42.5,
    "fullyAIModeRatio": 30.0,
    "mostlyAIModeRatio": 52.0
  },
  "DETAIL": [
    // 经处理后的存留 AI 占比行归置数组（按文件分类）
  ],
  "REPOSITORY": {
    "vcsType": "git",
    "repoURL": "https://github.com/EnigmaWU/MyGenCodeDescBase",
    "repoBranch": "main",
    "startTime": "2026-03-01T00:00:00Z",
    "endTime": "2026-03-31T23:59:59Z"
  }
}
```

*说明：所有的中间运行日志 (比如 `--log-level DEBUG` 触发的输出) 会全部被重定向至标准错误流 (`stderr`)，绝对不会干扰你对 `stdout` 中 JSON 数据的捕获或管道操作。*
