---
name: gntsp-model-swap
description: 火影忍者激斗忍者大战SP（Wii / GNTSP / 激闘忍者大戦!SP，光盘 ID 3800805）角色外观替换 —— 把来源角色 S 的模型、贴图、调色板换到目标角色 T 的选人槽位上，T 的骨架、动作、招式、动画全部保留。方法：同时改「散装」DATA/files/chr/<code>/ 与「打包」DATA/files/fpack/chr/<code>/0000.fpk 两处的外观文件（brres/brtex/brplt），保留 0000.mot 与 0000.seq 不动，用自带的 Eighting PRS 编解码器重建 FPK。含骨骼表实测数据（krn 78 / tnd 94 / hnt 106 / ino 127 根骨骼，共享骨骼编号但排列顺序不同）、Dolphin 目录版游戏测试流程、FPK 容器格式，以及「无效读取」误报等已知坑。Also usable for debugging such a mod that shows the original character, only changes some screens, crashes on entering battle, or whose FPK fails to load.
whenToUse: 当用户要求"把 X 的模型换到 Y 上""换了外观但招式不变""做一个火影 SP 的换皮 mod"，或需要排查这类 mod 没生效、只有部分画面变了、进战斗卡死/报错时使用。Use when swapping or replacing a character's model/appearance in Naruto Shippuuden Gekitou Ninja Taisen! SP (Wii, GNTSP, 3800805) or another Eighting FPK-based Clash of Ninja title.
---

# 火影忍者 激斗忍者大战SP（Wii）角色外观替换

目标：让目标角色 **T** 显示来源角色 **S** 的外观，**动作 / 招式 / 动画仍然是 T 的**。

> **方向先确认（最容易搞反）**："把 A 的模型换到 B 上" ⇒ **目标 T = B，来源 S = A**。
> 例："雏田替换夕日红" ⇒ `--slot krn --source hnt`（krn = 夕日红，hnt = 雏田）。

本仓库 `scripts/` 下是可直接运行的工具，均无第三方依赖（Python 3.8+）：

| 脚本 | 用途 |
|---|---|
| `scripts/swap_character.py` | 一键完成替换（散装 + FPK 两处），**主入口** |
| `scripts/verify_swap.py` | 交付前校验：逐文件比对，证明换对了、没换错 |
| `scripts/fpk_tool.py` | FPK 解包 / 重打包 / 自检（Eighting PRS 编解码） |
| `scripts/brres_bones.py` | 读骨骼表，解释"为什么不能整文件覆盖模型" |

---

## 0. 核心原理（先懂这个，后面全是推论）

角色数据存在**两个地方，内容重复**：

```
DATA/files/chr/<code>/0000.brres              散装文件
DATA/files/fpack/chr/<code>/0000.fpk          同样的文件，打包版
```

`main.dol` 里同时存在 `fpack/chr/%s/` 和 `chr/%s` 两种路径字符串，**两种都可能被读取**，
所以只改一处 ⇒ 某些画面仍是原角色。**两处都要改**（`swap_character.py` 自动都改）。

每个角色文件夹里的文件分工：

| 文件 | 作用 | 处理 |
|---|---|---|
| `0000.brres` | 主模型 | ← 取 S 的 |
| `0001.brres` | 副模型 | ← 取 S 的 |
| `0002.brres` | 第三形态 | ← 取 S 的 |
| `0100.brres` | 备用形态 / 另一套 | ← 取 S 的 |
| `0000.brtex` `0100.brtex` | 贴图 | ← 取 S 的 |
| `0000.brplt` `0100.brplt` | 调色板 | ← 取 S 的 |
| `0000.mot` | 动画 | **保留 T 的（整个方案的关键）** |
| `0000.seq` | 招式逻辑 | **保留 T 的** |

**为什么"换模型不换动画"能成立**：`0000.mot` 按**全局骨骼编号**驱动骨骼，
而不是按某个文件内的局部序号。各角色的骨骼表引用同一套编号空间：
krn 与 hnt 共享 35 个骨骼编号 —— 但**排列顺序不同**（35 个共享编号里只有 1 个落在相同槽位）。

**所以绝对不能整文件覆盖模型**：T 的动画会去驱动错误编号的骨骼 ⇒ 模型消失 / 扭成一团 / 进战斗崩溃。
正确做法是**只换网格 + 贴图 + 调色板**，动画与招式脚本原样保留。

用 `python scripts/brres_bones.py T.brres S.brres` 可以现场验证这一点。

## 1. 环境与原料

需要的原料：

1. **游戏镜像** `3800805.wbfs`（原始镜像，全程**只读不改**）。
2. **Dolphin 模拟器**。
3. **DolphinTool**（Dolphin 自带，用来把镜像解成目录版游戏）。
4. **原始游戏树底稿**：解包一次，长期保留，每次做新 mod 都从它复制。

## 2. 标准流程

### 步骤 1 — 把镜像解成「Dolphin 可直接运行的目录版」

```powershell
DolphinTool extract -i 3800805.wbfs -o <工作目录>\mod\game_root -g
```

`-g` 表示只解 DATA 分区。解出的目录里有 `DATA\sys\main.dol`，
Dolphin 直接「打开」这个 `main.dol` 就能运行，**不需要重打包 wbfs**。

这一步只需做一次。之后所有 mod 都从 `game_root` 复制。

### 步骤 2 — 一键替换

```powershell
python scripts\swap_character.py `
    --game-root <工作目录>\mod\game_root `
    --out       <工作目录>\mod\krn_as_hnt `
    --slot krn --source hnt
```

脚本会：

1. 把原始游戏树复制成新目录（跳过 `.svn`）；
2. 用 S 的 `brres/brtex/brplt` 覆盖 T 散装目录里的同名文件；
3. 解包 T 的原始 FPK（缓存到 `.work/<slot>_fpk_orig/`），
   把包内 `chr/<slot>/` 下的外观条目换成 S 的，**`0000.mot` / `0000.seq` 原样保留**，
   其余条目（`cam/` `cpu/` `eft/` `chr/cmn/`）一个字节都不动，然后重新打包；
4. 打印逐文件核对表（哪些来自 S、哪些保留 T、哪些仍是原角色）。

常用参数：

- `--mode full` —— 连动作、招式、特效一起换成 S 的（备用玩法；保留 T 招式时**不要**用）。
- `--fresh` —— 删掉已存在的 `--out` 重新构建。
- `--dry-run` —— 只报告会改什么，不写任何文件。

### 步骤 3 — 校验（交付前必做）

```powershell
python scripts\verify_swap.py `
    --out <工作目录>\mod\krn_as_hnt `
    --slot krn --source hnt `
    --game-root <工作目录>\mod\game_root
```

（如果构建时用了 `--mode full`，校验时也要加上 `--mode full`。）

它逐条检查四件事：

1. 散装外观文件是否与 S 逐字节相同；
2. `0000.mot` / `0000.seq` 是否与**原始版**逐字节相同（证明招式确实还是 T 的）；
3. FPK 内每个条目分类正确（外观来自 S、非外观仍是原版）；
4. 有没有哪个文件仍等于原角色（那意味着某个形态会显示旧模型）。

退出码 0 = 全部通过。

### 步骤 4 — 在 Dolphin 测试

```
Dolphin → 文件 → 打开 → <工作目录>\mod\krn_as_hnt\DATA\sys\main.dol
```

进**对战模式**，选 **T（本例是夕日红）**，应当看到 S（雏田）的外观。
再确认：动作、招式、胜利姿势仍是 T 的 —— 这才是正确结果。

**必须冷启动**：不要读战斗中的即时存档，模型不会重新加载。

## 3. 已知现象与坑

1. **「无效读取」报错是无害误报。**
   运行时会弹出（如：从 `0x00000050` 读取无效，`PC=0x8034c87c`，可能不止一条）。
   实测游戏正常运行，**直接无视**。
   **不要为此启用 Dolphin 的 MMU** —— 会明显变慢，甚至真的卡住。
2. **FPK 重压后一定变大**（例：`1187936 → 1287312`，约 +8.4%）。
   格式完全合法，游戏接受。这是 Eighting PRS 重压缩的正常结果，不是错误。
3. **原始 wbfs 镜像全程不改**。所有产物都是磁盘上的目录树。
4. **源角色缺某个文件** ⇒ 对应形态仍是原角色（例如 S 没有 `0002.brres`，
   而 T 有，那么那个形态保留 T 的原模型）。脚本会以 `WARN` 明确报出来 ——
   这是缺素材，不是替换失败。
5. **绝不要为了"省事"整文件覆盖 `.brres`** —— 见第 0 节的骨骼表原因。
6. `--game-root` 必须是**原始**树。拿已经改过的树当输入会叠加替换，结果不可预测。
7. 目录里可能有 `.svn` 等元数据文件夹，脚本会自动跳过，不要把它们打进 FPK。

## 4. 排错清单（"改了没生效"）

| 现象 | 最可能的原因 | 处理 |
|---|---|---|
| 完全没变化 | 测试的是旧目录 / 没冷启动 / 看错了角色槽位 | 确认 Dolphin 打开的是新构建的 `main.dol`，冷启动，选的是 **T** |
| 只有部分画面变了 | 只改了一处（散装或 FPK） | 用 `verify_swap.py` 检查，`swap_character.py` 本来两处都会改 |
| 某个形态 / 某套配色仍是原角色 | 源角色缺对应文件 | 看脚本的 `WARN` 行；属缺素材 |
| 进战斗崩溃、模型消失、扭成一团 | 动了 `0000.mot` / `0000.seq`，或整文件覆盖了 `.brres` | 回到原始树重做，只换外观文件 |
| FPK 解不开 / 游戏拒绝载入 | FPK 被别的方式重新打包过 | 只用本仓库 `fpk_tool.py`；先跑 `fpk_tool.py roundtrip <原版.fpk>` 自检 |
| 想确认某个角色代码是谁 | 猜代码 | 见 `references/character-codes.md`；不确定就逐个替换后用 Dolphin 肉眼确认 |

## 5. 角色代码

已在本作实测确认的代码（`--slot` / `--source` 用这些值）：

| 代码 | 角色 | 说明 |
|---|---|---|
| `krn` | 夕日红 | 三份成功记录里的目标槽位 |
| `tnd` | 纲手 | |
| `ino` | 井野 | |
| `hnt` | 雏田 | |

完整代码清单、以及"如何自己确认某个代码对应谁"，见
[`references/character-codes.md`](references/character-codes.md)。

## 6. 参考文档

- [`references/character-codes.md`](references/character-codes.md) —— 角色代码与自行核对方法
- [`references/file-formats.md`](references/file-formats.md) —— FPK 容器与 BRRES/MDL0 骨骼表结构
- [`references/troubleshooting.md`](references/troubleshooting.md) —— 更详细的排错与诊断命令
- [`references/measured-data.md`](references/measured-data.md) —— 本作实测数据（骨骼表、文件大小）
- [`references/success-records/`](references/success-records/) —— 三次成功制作的原始流程记录

## 附：脚本命名惯例（沿用更早的工作习惯）

```
build_swap_<source>.py     针对某个来源角色的替换脚本（本仓库已通用化为 swap_character.py）
.work/<slot>_fpk_orig/     某个槽位的原始 FPK 解包缓存，可复用、不要手改
```
